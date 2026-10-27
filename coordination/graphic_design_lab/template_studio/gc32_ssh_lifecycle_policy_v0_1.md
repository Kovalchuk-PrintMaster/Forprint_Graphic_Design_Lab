# GC32 · SSH inventory and compact lifecycle policy v0.1

**Scope:** s01 / existing GDL repository and the one existing PREPRESS root `D:\ForPrint_Automation\GraficsDesignLab\Automation`. Client workspace remains the authority for accepted sources and review outputs. No other root is created.

## Authoritative duties

- s01 owns intake acceptance, dispatch, resource pins, customer-owned files and the published HTML snapshot.
- PREPRESS / Work reads only its actual local tree via the already verified SSH key. No Windows -> SMB inventory writes; no Windows file copies for each inventory refresh.
- Client `template_studio/index.html` embeds the last verified snapshot at operator publication. It is not a live filesystem explorer.
- Standard resource cache is keyed by stable ID + SHA256; current work may not be inferred obsolete simply because a later attempt exists.

## Lifecycle categories (proposals only)

| State | Meaning | Action |
|---|---|---|
| `STRUCTURE_REGISTERED` | Root directory or exact worker control-plane file | Keep; monitor consistency |
| `REGISTERED_ACTIVE_OR_PINNED` | Declared client directory / resource vault | Keep; SHA check where pinned |
| `OUTPUT_EVIDENCE_REVIEW`, `SOURCE_INPUT_REVIEW`, `RELEASE_HISTORY_PROTECTED` | Possibly authoritative input, closeout evidence or portal history | Protect; compare lineage |
| `HISTORY_REVIEW`, `ATTEMPT_HISTORY_REVIEW` | Historical candidate/work attempt | Operator review and dependency scan |
| `UNCLASSIFIED_REVIEW` | Unmapped file | Register owner and purpose before further action |

## Future quarantine gate (not implemented here)

1. Take a fresh SSH/SMB snapshot and compare with the last registered snapshot; require complete scan.
2. Show owner/module, status, active path references, exact SHA256, acceptance/closeout evidence, last confirmed use and retention type.
3. Allow only an explicitly approved **exact write-set**; move to a quarantine area under the same existing root with a content hash, origin, timestamp and restore instructions, using no cross-volume silent loss.
4. Confirm unaffected worker preflight, tests, outputs and template rendering; keep immutable disposition receipt. Restore atomically if any contradiction appears.
5. Deletion is an independent future operator-authorized governance decision, **never a side effect of scan, build or refresh**.

No automatic deletion, glob-clean, move, job retry or workspace reorganization is permitted by this feature. The project `tmp/` contains only scan records and their history; actual artifacts remain in place.

## Refresh process

`make gc32-ssh-inventory-capture` runs SSH read-only and creates `tmp/gc32_ssh_inventory/<run>/prepress_snapshot.json` with `lifecycle_proposal.json`, `client_lifecycle_proposal.json`, and a bound manifest. Operator reviews, then `make gc32-ssh-inventory-publish` writes only the PREPRESS snapshot to client `template_studio/inventory/`; it preserves the previous snapshot in the run directory. `make gc32-portal-refresh` publishes the new view under the same HTML bookmark.

**Security:** authenticated SSH transport uses a pinned known_hosts file and private key already in the GDL remote-operator contract. UTF-16LE EncodedCommand transmits PowerShell without modifying ExecutionPolicy globally. The Windows script does not follow reparse points and does not traverse other client job payloads. The snapshot captures only file names, sizes and optional hashes of small approved file types, never file contents. Sources remain confidential in the operator's private HTML; avoid forwarding these inventories to third parties.
