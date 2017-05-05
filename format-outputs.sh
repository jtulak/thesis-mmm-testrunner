#!/usr/bin/env bash
if [ $# -ne 1 ]; then
	echo "Usage: $0 DIR"
	echo "Removes colors escape sequences from GCC.log"
	echo "and saves the clean output to GCC.log.nocolors"
	exit 0
fi

if [ -d "$1" ]; then
	for d in $(ls "$1"); do
		# remove shell escape codes for colors
		if [ -f "$1/$d/Clang.log" ]; then
			cat "$1/$d/Clang.log" | \
				sed -r "s/\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[mGK]//g" \
				> "$1/$d/Clang.log.nocolors"

			cat "$1/$d/Clang.log.nocolors" | \
				sed -n -e '/CURRENT DEFECTS/,$p' \
				> "$1/$d/Clang.log.cut"
		fi

		if [ -f "$1/$d/GCC.log" ]; then
			cat "$1/$d/GCC.log" | \
				sed -r "s/\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[mGK]//g" \
				> "$1/$d/GCC.log.nocolors"

			cat "$1/$d/GCC.log.nocolors" | \
				sed -n -e '/CURRENT DEFECTS/,$p' \
				> "$1/$d/GCC.log.cut"
		fi
	done
else
	echo "Error: $1 is not a directory!"
	exit 1
fi

