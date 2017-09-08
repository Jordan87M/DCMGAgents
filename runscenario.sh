#!/usr/bin/env bash

if [ $1 == "-h" ]
then 
    echo "./runscenario.sh <name of scenario>"
    exit 0
fi

if [ -z "$1" ]
then
    echo "no argument provided"
    exit 0
fi

sel=$1
echo $sel
echo "./scenarios/$sel"

if [ ! -d "./scenarios/$sel" ]
then
    echo "argument is not a directory in the scenarios folder"
    exit 0
fi

if [ -z "$VOLTTRON_HOME" ]
then
    VOLTTRON_HOME=$HOME/.volttron
    echo "VOLTTRON_HOME UNSET setting to $VOLTTRON_HOME"
fi
echo "VOLTTRON_HOME=$VOLTTRON_HOME"

echo "removing old log"
rm volttron.log

utility_path=./scenarios/$sel/utility
weather_path=./scenarios/$sel/weather
home_path=./scenarios/$sel/home

for file in $utility_path/*config*
do
    echo "$file"
    name=${file#*config}
    
    ./scripts/core/pack_install.sh ./DCMGClasses/Agents/UtilityAgent $file $name
done

for file in $weather_path/*config*
do
    echo "$file"
    name=${file#*config}

    ./scripts/core/pack_install.sh ./DCMGClasses/Agents/WeatherAgent $file $name
done


for file in $home_path/*config*
do
    echo "$file"
    name=${file#*config}

    ./scripts/core/pack_install.sh ./DCMGClasses/Agents/HomeAgent $file $name
done

VOLTTRON_HOME=$VOLTTRON_HOME volttron-ctl status

