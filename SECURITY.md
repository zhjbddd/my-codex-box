# Security Policy

## Supported versions

The latest commit on `main` is supported during the pre-1.0 phase. Security fixes are not
backported until versioned releases are available.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature under **Security → Advisories → New
draft security advisory**. Do not open a public issue for a suspected vulnerability and do not
include API keys, copyrighted books, personal documents, or production credentials in a report.

If private reporting is unavailable, open a minimal issue asking the maintainer to enable a private
channel without disclosing exploit details.

You should normally receive an acknowledgement within seven days. As a single-maintainer project,
fix timelines depend on severity and reproducibility; confirmed critical issues may result in a
temporary release warning or feature disablement.

## Maintained security boundary

We treat local books, EPUB members, extracted text, model output, paths, and contributions as
untrusted. Security-sensitive behavior includes:

- archive and XML parsing;
- filesystem writes below the selected output directory;
- prompt-injection resistance when book text is sent to a model;
- API credential handling and outbound requests, including session-only
  desktop-client key entry that must not be written to disk or command arguments;
- quote-verification logic and fail-closed filtering;
- Skill instructions that can influence an agent's shell, network, or file behavior.

The project does not execute scripts embedded in books and does not claim that a successful run
proves a book or generated summary is safe or correct.
