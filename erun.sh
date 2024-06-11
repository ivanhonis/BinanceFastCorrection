echo --------------------------------------
echo Kill all running Python process
echo --------------------------------------

ps aux
for KILLPID in `ps ax | grep 'python3' | awk ' { print $1;}'`; do
  echo kill pid $KILLPID;
  kill -9 $KILLPID;
done

read -p "Do you want to run TRADE_SERVER_FUTURES.py in the background? (y/n): " choice

if [ "$choice" = "y" ]; then
  echo --------------------------------------
  echo RUN TRADE_SERVER_FUTURES IN BACKGROUND
  echo --------------------------------------
  nohup python3 -u TRADE_SERVER_FUTURES.py > output.log 2>&1 &
else
  echo --------------------------------------
  echo RUN FCS
  echo --------------------------------------
  python3 TRADE_SERVER_FUTURES.py
fi

