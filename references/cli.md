# CLI reference

Run `python3 scripts/trello.py COMMAND --help` for exact syntax. Credentials come from process environment. IDs below are placeholders, not URLs. Shell snippets assume Bash or a compatible shell.

```sh
python3 scripts/trello.py boards
python3 scripts/trello.py lists BOARDID
python3 scripts/trello.py cards LISTID
python3 scripts/trello.py card CARDID
python3 scripts/trello.py create LISTID --name '[Service] Deliver outcome' --desc "$(cat templates/task.md)" --yes
python3 scripts/trello.py update CARDID --desc 'Complete replacement description' --yes
python3 scripts/trello.py move CARDID DESTINATIONLISTID --yes
python3 scripts/trello.py comment CARDID --text 'Verified result: evidence link' --yes
python3 scripts/trello.py copy TEMPLATEID LISTID --name '[Service] Deliver outcome' --keep checklists --yes
python3 scripts/trello.py labels BOARDID
python3 scripts/trello.py create-label BOARDID --name DEV --color green --yes
python3 scripts/trello.py assign-label CARDID LABELID --yes
python3 scripts/trello.py checklists CARDID
python3 scripts/trello.py create-checklist CARDID --name To-dos --yes
python3 scripts/trello.py add-checklist-item CHECKLISTID --name 'Verify outcome' --yes
python3 scripts/trello.py set-checklist-item CARDID ITEMID --state complete --yes
```

Read commands return JSON on stdout. Errors are sanitized JSON on stderr. Update can change --name and/or --desc; an empty description clears it. Copy --keep accepts checklists (default), all or none; this controls copied attributes, not authorization or privacy. Label color values are passed to Trello for validation. Alphanumeric IDs are syntax-checked but existence, membership and permissions remain API/user checks. Board/card read collections are bounded by API defaults; labels request at most 100. No complete-export guarantee.
