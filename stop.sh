pid=`pgrep -f 'python3.6 client.py'`

if [ -n "$pid" ]; then
    echo " stopping ..." && \
    sudo kill -9 $pid && \
    echo " stopped."
fi

