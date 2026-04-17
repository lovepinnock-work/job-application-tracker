## Architecture

### Structure
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
```

### Technical Highlights
- Designed an entity reconciliation system to merge noisy, multi-source email updates into stable application records
- Modeled many-to-many relationships between applications and hiring events
- Built a hybrid automation flow combining deterministic filtering, structured LLM extraction, and human review
- Engineered around free-tier API constraints using caching, batching, local logs, and processed-message labeling
- Integrated Gmail API, Google Sheets API, and structured LLM extraction into an end-to-end workflow

##  Design Decisions and Tradeoffs
### Why use LLM extraction instead of pure rules

Job emails vary too much across ATS vendors, recruiter messages, assessment platforms, and government hiring systems. Pure rules were too brittle for long-term use.

### Why keep a review queue

Ambiguous emails are safer when routed to manual review than when force-matched incorrectly. This was a deliberate design decision to favor correctness over aggressive automation.

### Why use Gmail labels plus local cache

The system uses both Gmail labels and a local processed-message cache to:

- avoid duplicate work
- reduce repeated API calls
- stay within free-tier limits

### Why not fully rely on Gemini

I operate within the free-tier quotas of Gemini to maintain accessability. Since we treat it as a limited resource, the system uses:

- local prefilters
- cached results
- processed labels
- delayed / bounded processing

## Review Queue Workflow

Ambiguous or weakly matched emails are written to ReviewQueue instead of being forced into the main tracker.

The interactive promotion helper supports:

- promoting a review row into an application
- promoting a review row into an event
- linking an event to an existing application
- clearing a non-relevant review row

This keeps the system practical while avoiding bad automation.

## Digests

The project includes:

- daily digest generation
- weekly digest generation

These summarize:

- tracked application counts
- current status distribution
- recent processing results
- review items

## Limitations

Because email formats vary widely across ATS vendors, recruiter workflows, and assessment providers, the system does not blindly trust every extraction. Ambiguous cases are routed to a review queue instead of risking incorrect updates.

The system is optimized for correctness and practical use rather than aggressive full automation.

## Future Improvements
- migrate Gmail polling to Gmail push notifications with Pub/Sub
- optional OpenAI fallback for tougher extraction cases
- richer review resolution tooling
- dashboard/UI on top of Sheets data
- persistent database backend instead of Sheets
- more ATS-specific deterministic parsers for high-frequency senders