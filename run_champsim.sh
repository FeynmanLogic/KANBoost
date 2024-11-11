# It's a comment../bin/bash
if [ "$#" -lt 4 ]; then
    echo "Illegal number of parameters"
    echo "Usage: ./run_champsim.sh [BINARY] [N_WARM] [N_SIM] [TRACE] [OPTION]"
    exit 1
fi

TRACE_DIR=$PWD/dpc3_traces
BINARY=${1}
N_WARM=${2}
N_SIM=${3}
TRACE=${4}
OPTION=${5}

# Sanity check for trace directory
if [ -z "$TRACE_DIR" ] || [ ! -d "$TRACE_DIR" ]; then
    echo "[ERROR] Cannot find a trace directory: $TRACE_DIR"
    exit 1
fi

# Check for binary file
if [ ! -f "bin/$BINARY" ]; then
    echo "[ERROR] Cannot find a ChampSim binary: bin/$BINARY"
    exit 1
fi

# Check if warmup instructions are numeric
re='^[0-9]+$'
if ! [[ $N_WARM =~ $re ]] || [ -z "$N_WARM" ]; then
    echo "[ERROR]: Number of warmup instructions is NOT a number" >&2
    exit 1
fi

# Check if simulation instructions are numeric
if ! [[ $N_SIM =~ $re ]] || [ -z "$N_SIM" ]; then
    echo "[ERROR]: Number of simulation instructions is NOT a number" >&2
    exit 1
fi

# Check if trace file exists
if [ ! -f "$TRACE_DIR/$TRACE" ]; then
    echo "[ERROR] Cannot find a trace file: $TRACE_DIR/$TRACE"
    exit 1
fi

# Create results directory and run the simulation
mkdir -p results_${N_SIM}M

(./bin/${BINARY} -warmup_instructions ${N_WARM}000000 -simulation_instructions ${N_SIM}000000 ${OPTION} -traces ${TRACE_DIR}/${TRACE}) &> results_${N_SIM}M/${TRACE}-${BINARY}${OPTION}.
