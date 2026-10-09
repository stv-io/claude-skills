---
name: browser-select
description: Resolve a friendly browser name (e.g. dia-work, dia-personal, chrome-work, chrome-client) to the deviceId the claude-in-chrome MCP tools need, and pick the right browser when none was named. Use BEFORE any mcp__claude-in-chrome__* tool call, whenever the user names a browser or profile, says "wrong browser"/"switch browser"/"use my work browser", when a browser action fails because the extension is disconnected or re-authenticated, or when registering a newly installed browser.
---

# Picking the right browser

The user runs several browsers against the same Claude account — different
profiles with different logins and permission boundaries. The MCP layer only
exposes an opaque `deviceId` and a generic extension name ("Browser 1"), so
sessions pick the wrong one. `~/.claude/browsers.json` maps friendly aliases to
deviceIds; the `browsers` CLI (`bin/browsers` in this skill, installed on your PATH) reads and maintains it.

**Using the wrong browser is a real failure, not a cosmetic one** — the wrong
profile means the wrong Google account, wrong Jira tenant, and work data
touched from a personal session.

## The rule

**Unless the user has named a profile, ask which one to use. Always. Never
choose on their behalf.**

That holds no matter how obvious the answer looks. Specifically, none of these
authorize picking one yourself:

- only one browser is connected
- one alias is marked default in the registry
- the task is plainly work-flavoured (a Jira ticket, a work doc) and only one
  work profile exists
- a browser is already selected from earlier in the session by something other
  than the user's choice
- the user is mid-task and asking feels like friction

The only thing that authorizes proceeding without asking is the user naming a
browser — this turn, or earlier in this session.

**Once they have chosen, that choice holds for the rest of the session.** Do
not re-ask before every tool call. Ask again only if they mention a different
profile, the task crosses a work/personal boundary, or the selected browser
stops responding.

The registry's default (`*` in `browsers list`) is **not** a licence to skip
the question. It only decides which option to list first, marked
"(Recommended)", in the question you still have to ask.

## The user named a browser

```bash
browsers get dia-work        # -> deviceId, or a non-zero exit with the reason
```

Pass that deviceId straight to `mcp__claude-in-chrome__select_browser`, say
which alias you selected, and continue with the normal flow
(`tabs_context_mcp`, `tabs_create_mcp`, …). No AskUserQuestion — they chose.

### What counts as naming one

Don't parse the phrasing yourself — hand the words straight to `browsers get`
and let it decide. It takes a whole phrase, and matches an exact alias, a
deviceId or its prefix, a fragment, or the alias/app/profile words appearing
anywhere in what was said:

```bash
browsers get use my personal browser     # -> dia-personal
browsers get in chrome                   # -> chrome-work
browsers get dia-work                    # -> <uuid>
```

**Exit code is the instruction:**

| Exit | Meaning | What to do |
|---|---|---|
| 0 | resolved | use the deviceId printed on stdout |
| 2 | ambiguous, candidates listed on stderr | ask, offering *only* those candidates |
| 1 | unknown alias, or registered but unbound | see the message — register it, or ask |

"my work browser" is exit 2 (both `dia-work` and `chrome-work`); so is "in dia"
while two Dia profiles exist. That is the tool refusing to guess, not a
failure — turn it into a question rather than picking the first one listed.

## No browser named

1. `browsers list` — the registered aliases and what each is for.
2. `mcp__claude-in-chrome__list_connected_browsers` — what is actually
   connected now.
3. Reconcile the two, which also refreshes `lastSeen`:

   ```bash
   echo '<the JSON list_connected_browsers returned>' | browsers sync
   ```

4. Ask with **AskUserQuestion**, one option per connected browser, labelled
   with the alias and its notes rather than "Browser 1" — plus the required
   final option, worded exactly:

   > Open a confirmation screen in every connected Chrome extension and let me select the right one there.

   That last one maps to `switch_browser`. Never pick a browser yourself.

Registered aliases that are **not currently connected** still belong in the
question, marked as such — "dia-personal (not connected; I'll ask you to open
it)". Otherwise the user silently loses the option of the browser they actually
wanted, which is how a session ends up doing personal work in a work profile.

If exactly one browser is connected, ask anyway — a one-option question is a
cheap confirmation, and "only one is connected" usually means the one they
wanted is closed or signed out, not that this is the right one.

## Registering a new browser

A deviceId is only visible while that browser is connected, so bind them one at
a time:

1. Open the browser, confirm the Claude extension is signed in and connected.
2. `mcp__claude-in-chrome__list_connected_browsers`.
3. Feed it through `browsers sync` — the new one shows up under
   "connected but UNKNOWN to the registry".
4. Confirm with the user which alias it is (nothing about the payload reveals
   whether a given Dia instance is the work or personal profile — do not guess),
   then bind:

   ```bash
   browsers add dia-personal --device-id <uuid> --app Dia --profile personal \
     --notes "personal logins only"
   ```

### Narrowing it down without bothering the user

If the candidates are different *apps*, a blank tab identifies the app with no
account data touched. Chrome refuses to run scripts on `chrome://newtab`, so
navigate somewhere neutral (`https://example.com`) first, then:

```js
(() => { const u = navigator.userAgent.toLowerCase();
  const b = ((navigator.userAgentData&&navigator.userAgentData.brands)||[]).map(x=>x.brand.toLowerCase()).join(",");
  const hit = n => u.includes(n) || b.includes(n);
  if (hit("dia")) return "DIA"; if (hit("arc")) return "ARC";
  if (hit("google chrome")) return "CHROME"; return "UNKNOWN"; })()
```

Return a classification, not the raw user-agent string — the raw UA trips a
content filter and comes back `[BLOCKED: Cookie/query string data]`.

Observed with Dia on macOS: Chrome → `CHROME`, Dia → `UNKNOWN` (Dia does not
advertise itself in the UA). So `UNKNOWN` on macOS usually means Dia, but it is
inference, not proof — and it can never separate **dia-work from
dia-personal**, which are the same app. For same-app profiles, ask the user, or
use `switch_browser` and have them click in the right window.

Also worth doing once per browser: call `switch_browser` and have the user
click Connect in the target browser and name it there (`dia-work`). That
renames it inside the extension, so even a session that never reads this
registry sees a meaningful name in the raw MCP listing.

## When it breaks

The extension's auth expires periodically, and re-authenticating or
reinstalling can mint a **new deviceId**. Symptoms: `select_browser` fails, or
a stored alias never appears in `list_connected_browsers`.

Run `browsers sync` first. It separates the two causes:

- alias listed under "registered but not connected" and nothing unknown showed
  up → that browser is closed or signed out. Ask the user to open it and sign
  the extension back in.
- an unknown deviceId appeared and one alias went missing → same browser, new
  id after a re-login. Confirm with the user, then rebind with
  `browsers add <alias> --device-id <new-uuid>`.

Do not silently rebind an alias to whatever id happens to be connected — that
is exactly how a work alias ends up pointing at the personal profile.

## Registry commands

```bash
browsers list                 # aliases, deviceIds, what each is for (* = default)
browsers list --json          # machine-readable
browsers get <alias>          # deviceId only — the one an agent usually wants
browsers add <alias> [...]    # register or update
browsers rm <alias>           # forget
browsers default [<alias>]    # show or set the default
browsers sync                 # reconcile vs live JSON on stdin
browsers path                 # where the registry lives
```
