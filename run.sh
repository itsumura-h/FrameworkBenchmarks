rm -fr ./results/*

# Options:
# --mode <benchmark|verify|debug>
# --test <test_name>
# --type <plaintext|json|query|cached-query|fortune|update>

# ./tfb --mode verify --test basolato

# ./tfb --mode benchmark \
#   --test basolato basolato-malloc basolato-httpbeast basolato-httpbeast-malloc basolato-httpx basolato-httpx-malloc \
#   --type plaintext json query

# ./tfb --mode benchmark \
#   --test basolato basolato-malloc basolato-httpbeast basolato-httpbeast-malloc basolato-httpx basolato-httpx-malloc \
#   --type plaintext json query

./tfb --mode benchmark --test basolato jester gin echo axum actix laravel django fastapi rails hono deno
# ./tfb --mode benchmark --test basolato

docker build -t fb-results-site -f toolset/results-site/Dockerfile toolset/results-site

docker run --rm \
  -v "$(pwd):/workspace:ro" \
  -v "$(pwd)/_site:/out" \
  fb-results-site --repo-root /workspace --out /out
