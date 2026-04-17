# Job Application Tracker

A backend automation project that ingests Gmail job-application emails, uses structured LLM extraction to classify updates, reconciles them into application and event records, stores results in Google Sheets, and routes ambiguous cases into a review queue for manual resolution.

## Why I built this

Job application emails vary widely across ATS platforms, recruiter emails, assessment providers, and company workflows. I built this project to automate the repetitive parts of tracking applications while still preserving accuracy through a human-in-the-loop review flow.

Instead of relying entirely on brittle keyword rules, the system combines deterministic filtering, structured LLM extraction, reconciliation logic, and manual review tooling. The result is a practical workflow that reduces repetitive tracking work without blindly trusting every email.

## Key Features

- Gmail polling for new application-related emails
- Structured LLM extraction for:
  - application confirmations
  - rejections
  - assessments
  - interviews
  - offers
  - cancellations
- Reconciliation logic to merge noisy updates into the correct application record
- Support for shared events, such as one assessment covering multiple applications
- Review queue for ambiguous emails instead of risky auto-updates
- Interactive helper scripts to promote review items into applications or events
- Daily and weekly digest generation
- Rate-limit-aware design for Gemini free tier
- Google Sheets persistence for:
  - Applications
  - Events
  - EventApplications
  - ReviewQueue

## Architecture

```text
Gmail Poller
  -> local prefilter
  -> LLM extraction
  -> reconciler
  -> Google Sheets
      - Applications
      - Events
      - EventApplications
      - ReviewQueue
  -> Gmail labels
      - Processed
      - Review
  -> digests + logs