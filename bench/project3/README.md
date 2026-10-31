# alerts

Sends alert messages to the team's alert service.

Setup: copy `.env.example` to `.env.local` and put your service token in it; the shell that runs the
app loads it (`set -a; . ./.env.local; set +a`).

Run the tests with `python3 -m unittest discover -s tests`.
