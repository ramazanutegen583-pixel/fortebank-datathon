# Technical requirements

This is a working summary of the ForteBank case specification and FAQ.
The original materials take precedence where this summary differs.

## User workflow

A user uploads a .mov video through the web interface, sees processing status,
and receives either no detected violation or signs of possible violations.

Each detected event includes a category, timestamp, observable description,
supporting frames, and a public rule reference. A video may contain multiple
events. The result supports human review and must not make conclusions that
depend on invisible banking-system data.

## Required public interface

- POST /api/v1/analyze accepts the multipart file field and returns job_id.
- GET /api/v1/jobs/{job_id} returns processing, done, or failed.
- Both endpoints require a valid X-API-Key header.
- Completed responses use violation or no_violation and the violations array.
- Each event includes type, timecode_sec, description, and evidence_frames.
- Each event includes 1–3 JPEG frames encoded as base64, with timestamp_sec.
- The violations array is empty for no_violation.
- An unavailable service or a result taking more than five minutes counts as
  an unprocessed video.
- The jury requires a publicly accessible service URL.

The exact project contract is documented in contracts/README.md.

## Processing and data restrictions

Processing runs inside the deployed service without external inference or
recognition APIs. Competition videos, frames, and their descriptions must not
be transmitted to external processing services. Once weights are installed,
video processing must work without internet access.

Audio processing and facial recognition or identification are prohibited.
Code, templates, and pretrained weights must have licenses allowing commercial
use. The organizers provide no GPU or cloud credits.

Competition materials may be used only for the event. Jury evaluation videos
must not be used for training, published, or transferred to third parties.
The FAQ identifies cloud API processing and ready-made solutions as grounds
for disqualification. It does not precisely define the boundary of a ready-made
solution.

## Dataset and generalization

The supplied archive contains 42 videos and a label sheet: 22 positive and
20 negative examples. Labels identify a timestamp and binary outcome but not
the event category. Event categories have not been established in this repository.

The FAQ describes .mov recordings lasting 10–145 seconds, at least 29 FPS,
without audio, with files around 29 MB. The approximate size is not an announced
strict upload maximum.

The final evaluation contains at least five videos and may include new event
types and a different camera angle. Use held-out local evaluation; filenames,
known hashes, and labels are not valid prediction mechanisms.

## Public rule references

The team researches public sources from Kazakhstan, including National Bank
regulations and adilet.zan.kz. The FAQ also permits public documents from other
banks and references without an exact section. Prefer precise, verified sections
when available.

Each result must connect an observable action to a real rule reference.
Do not fabricate citations or turn unavailable system information into a visual
finding.

## Scoring

| Criterion | Maximum points |
| --- | --- |
| Detection | 25 |
| Localization and evidence | 15 |
| Event classification | 15 |
| Rule justification | 15 |
| Generalization | 10 |
| Product readiness | 10 |
| Technical solution | 10 |
| Total | 100 |

## Submission

Provide the interface URL, API URL, jury key, launch instructions, architecture
and model description, public rule references, supported event types, limitations,
and known error cases.

Shortlisted teams have five minutes to present and two minutes for questions.
Slides are optional. ForteBank reserves the right to use the solution commercially.

The FAQ states a 12:00 deadline without a date or time zone. It also mentions
an insufficient-data verdict while the required API defines only two verdicts.
Use the required binary contract until clarified. Technical failures are failed
jobs, not an additional verdict.

User accounts, history, report export, and batch uploads are optional.
