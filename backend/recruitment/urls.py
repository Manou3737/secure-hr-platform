
from django.urls import path

from recruitment.views import (
    JobApplicationListCreateView,
    JobApplicationDetailView,
    JobApplicationAssignmentView,
    JobApplicationStatusView,
    JobPostingActionView,
    JobPostingCreateView,
    JobPostingDetailView,
    CandidateDetailView,
    CandidateListCreateView,
)

urlpatterns = [
    # Create a job posting
    path(
        "job-postings/",
        JobPostingCreateView.as_view(),
        name="job-posting-create",
    ),

    # Update a job posting
    path(
        "job-postings/<uuid:posting_id>/",
        JobPostingDetailView.as_view(),
        name="job-posting-detail",
    ),

    # Publish, close, or cancel a job posting
    path(
        "job-postings/<uuid:posting_id>/<str:action>/",
        JobPostingActionView.as_view(),
        name="job-posting-action",
    ),
        # List and create candidates
    path(
        "candidates/",
        CandidateListCreateView.as_view(),
        name="candidate-list-create",
    ),

    # Retrieve and update a candidate
    path(
        "candidates/<uuid:candidate_id>/",
        CandidateDetailView.as_view(),
        name="candidate-detail",
    ),
    path(
        "applications/",
        JobApplicationListCreateView.as_view(),
        name="application-list-create",
    ),
    path(
        "applications/<uuid:application_id>/",
        JobApplicationDetailView.as_view(),
        name="application-detail",
    ),
    path(
        "applications/<uuid:application_id>/assign/",
        JobApplicationAssignmentView.as_view(),
        name="application-assign",
    ),
    path(
        "applications/<uuid:application_id>/status/",
        JobApplicationStatusView.as_view(),
        name="application-status",
    ),
]
