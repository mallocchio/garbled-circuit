import argparse
from yao.garbler import Bob, Alice, LocalTest

def main(party):

    circuit_path = 'circuit/min.json'
    if party == 'alice':
        Alice(circuit_path).start()
    elif party == 'bob':
        Bob().listen()
    elif party == "table":
        LocalTest(circuit_path, print_mode='table').start()

def init():
    
    parser = argparse.ArgumentParser(description="Run Yao protocol.")
    parser.add_argument("party",
                        choices=["alice", "bob", "table"],
                        help="The yao party to run.")
    main(party=parser.parse_args().party)

init()