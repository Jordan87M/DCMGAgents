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

echo
echo "RUNNING A NEW SCENARIO: $sel"
echo

echo "REMOVING OLD LOG..."
rm volttron.log

utility_path=./scenarios/$sel/utility
weather_path=./scenarios/$sel/weather
home_path=./scenarios/$sel/home

#remove previously installed agents
echo
echo "REMOVING PREVIOUSLY INSTALLED AGENTS..."
for dir in $VOLTTRON_HOME/agents/*
do
    echo "removing $dir"
    rm -r $dir
done

#clearing removed agents
VOLTTRON_HOME=$VOLTTRON_HOME volttron-ctl clear

echo

for file in $utility_path/*config*
do
    name=${file#*config}
    echo "PACKING AND INSTALLING  $name"
    agentlist+=($name)
    ./scripts/core/pack_install.sh ./DCMGClasses/Agents/UtilityAgent $file $name
done

for file in $weather_path/*config*
do
    name=${file#*config}
    echo "PACKING AND INSTALLING $name"
    agentlist+=($name)
    ./scripts/core/pack_install.sh ./DCMGClasses/Agents/WeatherAgent $file $name
done


for file in $home_path/*config*
do
    name=${file#*config}
    echo "PACKING AND INSTALLING $name"
    agentlist+=($name)
    ./scripts/core/pack_install.sh ./DCMGClasses/Agents/HomeAgent $file $name
done

echo
VOLTTRON_HOME=$VOLTTRON_HOME volttron-ctl status

echo
#echo "here are all of the agents to start:"
#echo ${agentlist[@]}

for tag in ${agentlist[@]}
do
    echo "STARTING AGENT: $tag "
    VOLTTRON_HOME=$VOLTTRON_HOME volttron-ctl start --tag $tag
done
