# Instagram collection on your own laptop (setup, once)

Written 9 Nov 2026 for Eesha (same steps for Akshat with his own login). Your laptop collects Instagram posts for the
in-scope fitness creators, at the safe rate (130 page loads a day), into the shared Azure database.
It only READS public Instagram pages: no likes, follows or comments.

## 1. Code
```
git pull
python -m venv venv
venv\Scripts\pip install -r requirements.txt psycopg2-binary pyyaml
```

## 2. Database login
Shimona sends you your password privately. In the project folder, create a file `.env` (never commit it) with:
```
DATABASE_URL=postgresql://eesha:YOUR_PASSWORD@capstone-shimona-db.postgres.database.azure.com:5432/postgres?sslmode=require
```
(all on ONE line, no spaces). Your login can read and add data; it cannot delete anything.
The dry run in step 4 also checks that the connection works.
If it says timeout / connection refused: send Shimona your IP address ("what is my IP" on Google); she adds it in
Azure portal -> capstone-shimona-db -> Networking.

## 3. OpenCLI (lets the script read Instagram through your Chrome)
1. Install Node.js (LTS) if you don't have it.
2. `npm install -g @jackwener/opencli@1.8.8`
3. Install the OpenCLI Chrome extension (version 1.0.27) following the OpenCLI README, in the Chrome where you are
   signed in to Instagram with YOUR OWN account.
4. `opencli doctor` must show `Daemon: running` and `Extension: connected`.

## 4. First run (watch it once)
```
cd scripts\ingestion
..\..\venv\Scripts\python.exe instagram_daily.py --dry-run
..\..\venv\Scripts\python.exe instagram_daily.py
```
The dry run only prints which creators it would collect. The real run opens Instagram pages slowly (one every ~8
seconds) and stops by itself at the first sign of a block. Keep Chrome open while it runs.

## 5. Daily (optional, after the first run worked)
Windows Task Scheduler -> Create Basic Task -> daily, pick a time when the laptop is on and Chrome is open
(not 12:00, Shimona's laptop runs then) -> Start a program:
- Program: `<project folder>\venv\Scripts\python.exe`
- Arguments: `instagram_daily.py`
- Start in: `<project folder>\scripts\ingestion`

## Rules
- Never raise the 130/day cap, never run it twice at the same time, never share your password or .env.
- If Instagram shows a warning or asks you to verify: stop, tell the team, wait a day.
