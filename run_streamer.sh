#!/bin/bash
cd /tmp/markets-dashboard
python3 live_streamer.py >> live_streamer.log 2>&1
