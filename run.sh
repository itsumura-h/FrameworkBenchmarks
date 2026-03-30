# ./tfb --mode verify --test basolato
# ./tfb --mode verify --test basolato --type cached-query
# ./tfb --mode benchmark --test basolato --type cached-query
./tfb --mode benchmark --test basolato jester gin echo axum actix laravel django fastapi rails hono deno
# ./tfb --mode benchmark --test basolato echo