import os
# DB Connection
putEnv("DB_DRIVER", "postgres")
putEnv("DB_CONNECTION", "tfb-database:5432")
putEnv("DB_USER", "benchmarkdbuser")
putEnv("DB_PASSWORD", "benchmarkdbpass")
putEnv("DB_DATABASE", "hello_world")
putEnv("DB_MAX_CONNECTION", "498")
# Logging
putEnv("LOG_IS_DISPLAY", "false")
putEnv("LOG_IS_FILE", "false")
putEnv("LOG_DIR", "/root/projects/FrameworkBenchmarks/frameworks/Nim/basolato/logs")
# Security
putEnv("SECRET_KEY", "E1-p|w>6%!FhXp~XWjQy;PWc") # 24 length
putEnv("CSRF_TIME", "525600") # minutes of 1 year
putEnv("SESSION_TIME", "20160") # minutes of 2 weeks
putEnv("SESSION_DB", "/root/projects/FrameworkBenchmarks/frameworks/Nim/basolato/session.db")
putEnv("IS_SESSION_MEMORY", "false")
