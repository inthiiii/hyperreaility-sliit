# Data origins and attribution

## Public geographic context
Source: geoBoundaries Sri Lanka ADM2 layer, boundary ID `LKA-ADM2-46371173`, sourced from OpenStreetMap and Wambacher. Metadata reports year represented 2017, source update January 2023 and build December 2023. Download links point to geoBoundaries repository revision `9469f09`.

The layer's metadata identifies **Open Data Commons Open Database License 1.0 (ODbL 1.0)**. Retain attribution to OpenStreetMap contributors, the source metadata, and the accompanying `CITATION-AND-USE-geoBoundaries.txt`. The fact that the API path says `gbOpen` does not replace this layer's explicit licence. Follow the upstream ODbL attribution and database-sharing obligations when distributing a derivative database.

- https://www.geoboundaries.org/api/current/gbOpen/LKA/ADM2/
- https://www.openstreetmap.org/copyright
- https://opendatacommons.org/licenses/odbl/1-0/

Downloaded bytes and URLs are recorded in `raw/geoboundaries/download_manifest.json`; the processing manifest records SHA-256 checksums. The processed subset retains the source geometries and source attribution.

## Synthetic operational inputs
All telecom sites, service dependencies, failures, roads, travel times, repair durations, crews, generators, priorities and incident reports in this pack are fictional fixtures generated for RE:L!NK. No operator, subscriber, hospital or emergency agency supplied these operational records. They have not been externally validated. The team should decide an explicit publication licence for its original project materials; this note does not override upstream geographic licences.

## Generation and research disclosure
Planning, Python data scripts and scenario drafts were prepared with ChatGPT/Codex assistance. The team must review the files and record the actual assistant/model identities visible to them in `docs/PROJECT_DETAILS.md`. No hosted inference service was called to generate these fixtures through the team's key. Do not list a guessed upstream model as an observed fact.
