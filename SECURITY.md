# Security policy

## Reporting a vulnerability

Do not file a public issue containing credentials, exploit details that affect users, or private log data. The GitHub repository has private vulnerability reporting enabled. Use [Report a vulnerability](https://github.com/Mhdjamadi1994/errdoc-cli/security/advisories/new); submissions through this route are private to the maintainers. If GitHub reporting is unavailable, contact the maintainer privately at [mohamadhasanjamadi1994@gmail.com](mailto:mohamadhasanjamadi1994@gmail.com). Do not include credentials or private logs in an initial email unless necessary to explain the issue.

## Current security limitations

- Log redaction covers common credential assignments, URL user information, Basic/Bearer/Token authorization values, and PEM private-key blocks, but still uses heuristics and may miss unusual formats. Review logs before sending them to a remote model provider.
- Runtime context omits the working directory, and known IPv4/IPv6 values and common home-directory paths are redacted. This does not hide the source network IP from GitHub or a remote model provider; the network service receives connections from the user's network.
- Command output, file logs, piped input, and LLM response bodies have fixed size limits; earlier captured output is omitted and marked.
- Model output is untrusted. Suggested commands may be incorrect or irrelevant.
- Model-generated command execution is disabled. User-entered commands can run only after confirmation inside the isolated container. Do not treat the blacklist as the security boundary.
- A public release must not enable execution until the isolated runtime has passed the acceptance criteria in QUALITY_GATES.md.

## Supported versions

No stable public version is currently supported. Report issues against the exact commit or prerelease artifact used.
