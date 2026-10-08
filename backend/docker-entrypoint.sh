#!/bin/sh
# Container start-up: migrate -> ensure synthetic data -> ensure a trained model -> seed -> serve.
set -e

echo "Applying database migrations..."
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  if alembic upgrade head; then break; fi
  echo "Database not ready (attempt $attempt), retrying in 3s..."
  sleep 3
done

if [ ! -f data/appointments.csv ]; then
  echo "Generating SYNTHETIC dataset..."
  python -m app.ml.generate_data
fi

if [ ! -f models/no_show_model.pkl ]; then
  echo "No model found - training..."
  python -m app.ml.train --source csv
fi

echo "Seeding database (idempotent)..."
python -m app.scripts.seed

exec "$@"
