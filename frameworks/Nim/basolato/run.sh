nohup ./main5000 2>&1 /dev/null &
nohup ./main5001 2>&1 /dev/null &
nohup ./main5002 2>&1 /dev/null &
nohup ./main5003 2>&1 /dev/null &

nginx -c /basolato/basolato_nginx.conf -g "daemon off;"
