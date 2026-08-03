#!/bin/bash
# Augmente le volume même avec un Multi-Output device actif
SwitchAudioSource -s "MacBook Pro Speakers" -t output
sleep 0.1
current=$(osascript -e "output volume of (get volume settings)")
new=$((current + 10))
if [ $new -gt 100 ]; then new=100; fi
osascript -e "set volume output volume $new"
sleep 0.1
SwitchAudioSource -s "TargetCo Output" -t output
