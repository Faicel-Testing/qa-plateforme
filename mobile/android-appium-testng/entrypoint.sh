#!/usr/bin/env bash
set -euo pipefail

echo "==> Java:"
java -version || true
echo "==> Maven:"
mvn -version || true

APPIUM_URL="${APPIUM_URL:-http://host.docker.internal:4723}"
SUITE="${SUITE_XML:-testng.xml}"

echo "==> Using APPIUM_URL=$APPIUM_URL"
echo "==> Using SUITE_XML=$SUITE"

# Exemple: passer l’URL Appium à la JVM si ton code lit une system property
MVN_ARGS=(
  -Dsurefire.suiteXmlFiles="$SUITE"
  -Dappium.url="$APPIUM_URL"
  -DskipTests=false
)

# logs + artefacts
mvn -B -e clean test "${MVN_ARGS[@]}"

echo "==> Tests finished."
