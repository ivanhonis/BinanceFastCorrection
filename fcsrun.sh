echo --------------------------------------
echo Kill all running Python process
echo --------------------------------------

ps aux
for KILLPID in `ps ax | grep 'python3' | awk ' { print $1;}'`; do
  echo kill pid $KILLPID;
  kill -9 $KILLPID;
done

#echo --------------------------------------
#echo RUN FCS
#echo --------------------------------------
#python3 TRADE_SERVER.py

echo --------------------------------------
echo RUN FCS IN BACKGROUND
echo --------------------------------------
nohup python3 TRADE_SERVER.py > output.log 2>&1 &
