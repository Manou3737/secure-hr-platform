
"""ClamAV streaming scanner for private HR document uploads."""

import os
import socket
import struct


class AntivirusUnavailable(Exception):
    """Raised when the antivirus service cannot scan a file."""


class MalwareDetected(Exception):
    """Raised when ClamAV detects malware."""


def scan_uploaded_file(uploaded_file):
    """Scan an uploaded file through ClamAV's INSTREAM protocol."""
    host = os.environ.get("CLAMAV_HOST", "clamav")
    port = int(os.environ.get("CLAMAV_PORT", "3310"))
    timeout = float(os.environ.get("CLAMAV_TIMEOUT", "30"))

    original_position = uploaded_file.tell()

    try:
        with socket.create_connection(
            (host, port),
            timeout=timeout,
        ) as connection:
            connection.settimeout(timeout)
            connection.sendall(b"zINSTREAM\0")

            while True:
                chunk = uploaded_file.read(64 * 1024)
                if not chunk:
                    break

                connection.sendall(struct.pack("!I", len(chunk)))
                connection.sendall(chunk)

            connection.sendall(struct.pack("!I", 0))

            response = bytearray()
            while not response.endswith(b"\0"):
                chunk = connection.recv(4096)
                if not chunk:
                    raise AntivirusUnavailable(
                        "ClamAV closed the connection without a result."
                    )
                response.extend(chunk)

                if len(response) > 8192:
                    raise AntivirusUnavailable(
                        "ClamAV returned an invalid response."
                    )

        result = response.rstrip(b"\0").decode(
            "utf-8",
            errors="replace",
        )

        if result.endswith("OK"):
            return

        if "FOUND" in result:
            raise MalwareDetected("The uploaded file is malicious.")

        raise AntivirusUnavailable(
            "ClamAV could not complete the scan."
        )

    except MalwareDetected:
        raise
    except (OSError, socket.timeout, ValueError, struct.error) as exc:
        raise AntivirusUnavailable(
            "The antivirus service is unavailable."
        ) from exc
    finally:
        uploaded_file.seek(original_position)
