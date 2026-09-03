# How to test the MO2 Load Order Auditor

Thanks for helping test this. It should take about five minutes.

## What this is

It's a read-only auditor for your Mod Organizer 2 setup. It reads your
left-pane mod priority and your plugin load order and flags problems LOOT
doesn't catch — things like a generated FNIS or BodySlide output mod being
overwritten by something above it, or a mod that's disabled while its plugin
is still ticked.

https://github.com/user-attachments/assets/98a912d9-2768-4c0e-969d-abb6340725c3

**It never changes anything.** It only reads files, and it makes no network
calls at all — nothing is uploaded, nothing phones home. You can run it with
MO2 open.

## What you need

- **Python 3.10 or newer.** That's it.
- **Nothing to install.** No `pip install`, no dependencies — it uses only
  Python's standard library.

To check if you already have Python, open a terminal and type:

```
python --version
```

If that prints `Python 3.10.x` or higher, you're set. If it says the command
isn't recognized, install Python from [python.org](https://www.python.org/downloads/)
and **tick "Add python.exe to PATH"** on the first screen of the installer.

## Running it

### 1. Unzip

Unzip `mo2audit-engine.zip` anywhere — Desktop or Downloads is fine. You'll
get a folder called `mo2audit-engine`.

### 2. Open a terminal in that folder

In File Explorer, open the `mo2audit-engine` folder, then either:

- Click the address bar, type `powershell`, and press Enter, **or**
- Hold **Shift**, right-click in the empty space, and choose
  *"Open PowerShell window here"* / *"Open in Terminal"*.

You should now have a terminal whose prompt shows the `mo2audit-engine`
folder.

### 3. Find your MO2 profile folder

This is the one step people get stuck on, so here it is in detail. You need
the path to the **profile folder** — the one containing `modlist.txt` and
`plugins.txt`.

It depends on how MO2 was installed:

**Portable instance** (MO2 keeps everything in its own install folder — you
picked "Portable" during setup):

```
<wherever MO2 is installed>\profiles\<YourProfileName>
```

For example: `C:\Games\MO2\profiles\Default`

**Global instance** (the default; MO2 stores data under your user folder):

```
%LOCALAPPDATA%\ModOrganizer\<InstanceName>\profiles\<YourProfileName>
```

For example:
`C:\Users\YourName\AppData\Local\ModOrganizer\Skyrim Special Edition\profiles\Default`

**Not sure which you have?** Easiest way: in MO2, click the **Tools** icon →
**Settings** → **Paths** tab. It shows the base directory. Your profile
folder is that path plus `\profiles\<YourProfileName>`.

**Shortcut:** paste `%LOCALAPPDATA%\ModOrganizer` into File Explorer's
address bar. If a folder opens with your instance in it, you're on a global
instance. Navigate into it → `profiles` → your profile, then copy the path
from the address bar.

### 4. Run it

In the terminal, run this with your own profile path in the quotes:

```
python -m mo2audit --profile-dir "C:\Games\MO2\profiles\Default"
```

Keep the quotes — paths with spaces need them.

You'll get a summary and a list of findings, grouped by severity.

> By default it shows at most 10 findings per check type. Add `--full` at the
> end to see every one.

## Sending the results back

Run it again with these flags to save the output to files:

```
python -m mo2audit --profile-dir "C:\Games\MO2\profiles\Default" --json findings.json --markdown report.md
```

That creates two files in the `mo2audit-engine` folder:

- **`findings.json`** — **this is the one to send back.** It's the complete
  findings list, never truncated.
- `report.md` — a readable version, handy if you want to skim what it found
  or paste it into a forum post.

Send me `findings.json`. If anything looked odd, `report.md` alongside it is
helpful too.

## Two things to expect (no need to report these)

**1. On Anniversary Edition builds, it flags two Creation Club files as
"orphaned":**

```
[ORPHANED_PLUGIN] ccBGSSSE001-Fish.esm is listed but not owned by any enabled mod
[ORPHANED_PLUGIN] _ResourcePack.esl is listed but not owned by any enabled mod
```

These are fine. They live in the game's own Data folder rather than in a
managed mod, and they load correctly. It's a known limitation that's already
on the fix list — **don't remove them from your plugin list.**

If you see *other* findings that look wrong, that's exactly the feedback I'm
after.

**2. Ignore the Install section in `README.md`.** It mentions `git clone` and
`pytest` — that's for working on the full source repo, not for this test
build. Everything you need is in this guide.

## Feedback

If anything looks wrong, confusing, or just plain incorrect about your setup —
tell me. False alarms are as useful to me as real catches.
