# How to Back Up Your iPhone to Your Mac

PyMessage reads your iMessage history from an iPhone backup stored on your Mac.
Before you can use PyMessage, you need to create this backup.

This guide walks you through the entire process step by step — no technical
experience required.

---

## Why Do You Need a Backup?

When you back up your iPhone to your Mac, your Mac stores a complete copy of
your phone's data — including your entire iMessage history — in a folder on
your hard drive. PyMessage reads directly from that folder.

Without a backup, PyMessage has no data to read.

!!! note "Does this affect my phone?"
    Backing up your iPhone does **not** delete or change anything on your
    phone. Your messages, photos, and apps stay exactly as they are.
    The backup is just a copy stored on your Mac.

---

## What You Need

- An iPhone
- A Mac running macOS 10.15 (Catalina) or later
- A Lightning or USB-C cable (the same one you use to charge your iPhone)
- 10–30 minutes (the first backup takes longer; later ones are faster)

---

## Step 1: Connect Your iPhone to Your Mac

1. Plug your charging cable into your iPhone and into a USB port on your Mac.
2. Unlock your iPhone by entering your passcode or using Face ID / Touch ID.
3. If a prompt appears on your iPhone that says **"Trust This Computer?"**, tap **Trust**. You will then be asked to enter your iPhone passcode — do so.

!!! warning "Don't skip the Trust step"
    If you tap "Don't Trust" by accident, your Mac will not be able to see your
    iPhone. See the [Troubleshooting](#troubleshooting) section below to fix this.

---

## Step 2: Open Finder

1. Click the **Finder** icon in your Dock. It looks like a two-toned blue and white smiling face.

    If you can't find the Dock, it's the row of icons along the bottom edge of your screen (or on the left or right side if you have moved it).

2. A Finder window will open showing your files and folders.

---

## Step 3: Select Your iPhone in the Sidebar

1. Look at the left side of the Finder window. You'll see a list of locations, including your Mac's hard drive and any connected devices.
2. Under the **Locations** heading, you should see your iPhone listed by name (for example, "Sarah's iPhone" or "iPhone").
3. Click your iPhone's name to open its summary page.

!!! tip "Don't see your iPhone in the sidebar?"
    Try these steps in order until it appears:

    1. Unplug the cable and plug it back in firmly.
    2. Make sure your iPhone screen is on and unlocked.
    3. Check that you tapped **Trust** on your iPhone when the prompt appeared.
    4. Try a different USB port on your Mac, or a different cable.
    5. Quit Finder completely (right-click the Finder icon in the Dock → **Quit**),
       then reopen it.

---

## Step 4: Configure the Backup

1. On your iPhone's summary page in Finder, scroll down until you see the **Backups** section.
2. Look for two options — one for backing up to iCloud and one for backing up to your Mac. Select **"Back up all of the data on your iPhone to this Mac"**.

    !!! note
        If you leave it set to iCloud, the backup will not be stored on your Mac
        and PyMessage will not be able to find it.

3. Click the **Back Up Now** button.

The backup will begin immediately. A progress bar appears near the top of the Finder window — it may say something like "Backing up…"

---

## Step 5: Wait for the Backup to Finish

The backup can take anywhere from a few minutes to about 30 minutes, depending on how much data is on your iPhone.

**While the backup runs:**

- Keep your iPhone connected. Do not unplug the cable until it finishes.
- You can use your Mac normally — browse the web, open other apps, etc.
- Your iPhone screen may go to sleep. That is fine; the backup will continue.

**You'll know it's done when:**

- The progress bar at the top of the Finder window disappears.
- The **Latest Backup** line in the Backups section updates to show today's date and the current time.

---

## Step 6: Verify the Backup Worked

Once the progress bar is gone:

1. In Finder, look at your iPhone's page under the **Backups** section.
2. Check the **Latest Backup** date and time. It should show today's date and a time within the last few minutes.

If it shows today's date, your backup was successful. You're ready to use PyMessage.

---

## Where Is the Backup Stored on Your Mac?

iPhone backups are saved to this folder on your Mac:

```
~/Library/Application Support/MobileSync/Backup/
```

Each backup lives in its own subfolder with a long name made of letters and
numbers (for example, `00008030-001A2B3C4D5E6F78`). That is completely normal —
you don't need to open or touch those folders.

PyMessage finds the backup automatically:

```python
from pymessage import find_backups

backups = find_backups()
for backup in backups:
    print(backup.device_name, backup.last_backup)
```

---

## Troubleshooting

### "Trust This Computer?" never appeared on my iPhone

- Unplug and re-plug the cable while your iPhone is unlocked.
- If you previously tapped "Don't Trust," go to **Settings → General → Transfer or Reset iPhone → Reset → Reset Location & Privacy** on your iPhone, then reconnect.

### The progress bar seems frozen

- Check that your iPhone screen hasn't gone to sleep — tap it to wake it up.
- If no progress has been made for more than 5 minutes, unplug the iPhone, close Finder, wait 30 seconds, reopen Finder, reconnect the iPhone, and click **Back Up Now** again.

### "Back Up Now" is grayed out

- Make sure **"Back up all of the data on your iPhone to this Mac"** is selected (not the iCloud option).
- Try force-quitting Finder: press **Command + Option + Escape**, select **Finder**, then click **Relaunch**.

### `find_backups()` returns an empty list after backing up

Wait a moment and try again — occasionally the system takes a minute to index a freshly created backup.

If it still returns empty, you can pass the backup path directly:

```python
from pymessage import get_messages

# Replace YOUR-BACKUP-ID with the folder name you find in the next step
df = get_messages("~/Library/Application Support/MobileSync/Backup/YOUR-BACKUP-ID")
```

To find `YOUR-BACKUP-ID`:

1. In Finder, press **Command + Shift + G**.
2. Paste `~/Library/Application Support/MobileSync/Backup/` and press **Enter**.
3. You'll see one or more folders with long names — use the one that was most recently modified.

---

## Next Steps

Your iPhone is backed up and you're ready to go:

- [Quick Start](index.md#quick-start) — Get your first DataFrame in minutes
- [Code Examples](code-examples.md) — Common usage patterns
- [API Reference](API.md) — Complete function documentation
