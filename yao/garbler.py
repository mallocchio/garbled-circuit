import logging
from abc import ABC, abstractmethod

from yao import ot, util, yao, garbler_utils

logging.basicConfig(format="[%(levelname)s] %(message)s", level=logging.WARNING)

class YaoGarbler(ABC):
    """An abstract class for Yao garblers (e.g., Alice)."""
    def __init__(self, circuits):
        parsed_circuits = util.parse_json(circuits)
        self.name = parsed_circuits["name"]
        self.circuits = [self._initialize_circuit(circuit) for circuit in parsed_circuits["circuits"]]

    def _initialize_circuit(self, circuit):
        garbled_circuit = yao.GarbledCircuit(circuit)
        pbits = garbled_circuit.get_pbits()
        return {
            "circuit": circuit,
            "garbled_circuit": garbled_circuit,
            "garbled_tables": garbled_circuit.get_garbled_tables(),
            "keys": garbled_circuit.get_keys(),
            "pbits": pbits,
            "pbits_out": {w: pbits[w] for w in circuit["out"]},
        }

    @abstractmethod
    def start(self):
        pass

class Alice(YaoGarbler):
    """Alice is the creator of the Yao circuit.
    
    Alice creates a Yao circuit and sends it to the evaluator along with her
    encrypted inputs. Alice will finally print the truth table of the circuit
    for all combinations of Alice-Bob inputs.
    """
    def __init__(self, circuits, oblivious_transfer=True):
        super().__init__(circuits)
        self.socket = util.GarblerSocket()
        self.ot = ot.ObliviousTransfer(self.socket, enabled=oblivious_transfer)
        self.alice_inputs = garbler_utils.read_input(garbler_utils.ALICE_DATA_PATH)

    def start(self):
        """Start Yao protocol."""
        for circuit in self.circuits:
            self._send_circuit(circuit)
            self.print_circuit(circuit)

    def _send_circuit(self, circuit):
        to_send = {
            "circuit": circuit["circuit"],
            "garbled_tables": circuit["garbled_tables"],
            "pbits_out": circuit["pbits_out"],
        }
        logging.debug(f"Sending {circuit['circuit']['id']}")
        self.socket.send_wait(to_send)

    def print_circuit(self, entry):
        circuit, pbits, keys = entry["circuit"], entry["pbits"], entry["keys"]
        a_wires, b_wires, outputs = circuit.get("alice", []), circuit.get("bob", []), circuit["out"]
        a_inputs = self._prepare_alice_inputs(a_wires, keys, pbits)
        b_keys = self._prepare_bob_keys(b_wires, keys, pbits)

        print(f"Sending {circuit['id']}...")

        result = self.ot.get_result(a_inputs, b_keys)
        str_result = ''.join([str(result[w]) for w in outputs])

        self.alice_to_bob_OT(min(self.alice_inputs), str_result, a_inputs, b_keys)

        garbler_utils.verify_output(garbler_utils.from_bin_to_decimal(str_result))

        print(f"Yao protocol computation completed successfully.\n"
                "Output has been saved to 'output/result.txt'.\n"
                "Please review the output file for detailed results.")


    def _prepare_alice_inputs(self, a_wires, keys, pbits):
        bits_a = [int(i) for i in list(f"{min(self.alice_inputs):b}".zfill(8))]
        return {
            a_wires[i]: (keys[a_wires[i]][bits_a[i]], pbits[a_wires[i]] ^ bits_a[i])
            for i in range(len(a_wires))
        }

    def _prepare_bob_keys(self, b_wires, keys, pbits):
        return {
            w: self._get_encr_bits(pbits[w], key0, key1)
            for w, (key0, key1) in keys.items() if w in b_wires
        }

    def alice_to_bob_OT(self, alice_min, str_result, a_inputs, b_keys):
        details = [
            "Alice's computation:\n",
            f" Alice's min number: {alice_min} ({garbler_utils.from_decimal_to_bin(alice_min)} in binary)",
            f" Alice's message for Bob: {str_result}\n",
            " Oblivious Transfer Details:\n",
            "  Alice's inputs:"
        ]
        details += [f"   Wire {wire}: Key = {key}, Encrypted Bit = {encr_bit}" for wire, (key, encr_bit) in a_inputs.items()]
        details.append("\n"
                       "  Keys sent to Bob to evaluate the circuit:\n")
        details += [
            f"   Wire {wire}:\n"
            f"    Key0 = {key0[0].decode('utf-8')}, Encrypted Bit0 = {key0[1]}\n"
            f"    Key1 = {key1[0].decode('utf-8')}, Encrypted Bit1 = {key1[1]}\n"
            for wire, (key0, key1) in b_keys.items()]
        garbler_utils.write_to_file("\n".join(details))

    def _get_encr_bits(self, pbit, key0, key1):
        return (key0, 0 ^ pbit), (key1, 1 ^ pbit)

class Bob:
    """Bob is the receiver and evaluator of the Yao circuit.
    
    Bob receives the Yao circuit from Alice, computes the results and sends
    them back.
    """
    def __init__(self, oblivious_transfer=True):
        self.socket = util.EvaluatorSocket()
        self.ot = ot.ObliviousTransfer(self.socket, enabled=oblivious_transfer)
        self.bob_inputs = garbler_utils.read_input(garbler_utils.BOB_DATA_PATH)

    def listen(self):
        """Start listening for Alice's messages."""
        logging.info("Start listening")
        try:
            for entry in self.socket.poll_socket():
                self.socket.send(True)
                self.send_evaluation(entry)
        except KeyboardInterrupt:
            logging.info("Stop listening")

    def send_evaluation(self, entry):
        circuit, pbits_out = entry["circuit"], entry["pbits_out"]
        garbled_tables = entry["garbled_tables"]
        b_wires = circuit.get("bob", [])
        b_inputs_clear = self._prepare_bob_inputs(b_wires)

        print(f"Received {circuit['id']}...")

        garbler_utils.write_to_file(clear=True)

        print(f"Evalueating the circuit...")
        self.bob_to_alice_OT(min(self.bob_inputs), b_inputs_clear, pbits_out)

        print(f"Circuit evaluated")

        print(f"Sending the results to Alice...")
        self.ot.send_result(circuit, garbled_tables, pbits_out, b_inputs_clear)

    def _prepare_bob_inputs(self, b_wires):
        bits_b = [int(i) for i in list(f"{min(self.bob_inputs):b}".zfill(8))]
        return {b_wires[i]: bits_b[i] for i in range(len(b_wires))}

    def bob_to_alice_OT(self, bob_min, b_inputs_clear, pbits_out):
        details = [
            "Bob's computation:\n",
            f" Bob's min number: {bob_min} ({garbler_utils.from_decimal_to_bin(bob_min)} in binary)",
            f" Bob's message for Alice: {''.join(map(str, pbits_out.values()))}\n",
            " Oblivious Transfer Details:\n",
            "  Bob's Inputs:"
        ]
        details += [f"   Wire {wire}: Bit = {bit}" for wire, bit in b_inputs_clear.items()]
        details.append("\n""  Bob's Output P-bits:")
        details += [f"   Wire {wire}: P-bit = {pbit}" for wire, pbit in pbits_out.items()]
        garbler_utils.write_to_file("\n".join(details))
        garbler_utils.write_to_file("\n\n")

class LocalTest(YaoGarbler):
    """A class for local tests to print a circuit evaluation or garbled tables."""
    def __init__(self, circuits, print_mode="circuit"):
        super().__init__(circuits)
        self._print_mode = print_mode
        self.modes = {
            "circuit": self._print_evaluation,
            "table": self._print_tables,
        }
        logging.info(f"Print mode: {print_mode}")

    def start(self):
        """Start local Yao protocol."""
        for circuit in self.circuits:
            self.modes[self.print_mode](circuit)

    def _print_tables(self, entry):
        """Print garbled tables."""
        entry["garbled_circuit"].print_garbled_tables()

    def _print_evaluation(self, entry):
        """Print circuit evaluation."""
        circuit, pbits, keys = entry["circuit"], entry["pbits"], entry["keys"]
        garbled_tables, outputs = entry["garbled_tables"], circuit["out"]
        a_wires, b_wires = circuit.get("alice", []), circuit.get("bob", [])
        pbits_out = {w: pbits[w] for w in outputs}
        N = len(a_wires) + len(b_wires)

        print(f"======== {circuit['id']} ========")

        for bits in [format(n, 'b').zfill(N) for n in range(2**N)]:
            a_inputs, b_inputs = self._prepare_inputs(bits, a_wires, b_wires, keys, pbits)
            result = yao.evaluate(circuit, garbled_tables, pbits_out, a_inputs, b_inputs)
            self._print_result(bits, a_wires, b_wires, outputs, result)

    def _prepare_inputs(self, bits, a_wires, b_wires, keys, pbits):
        bits_a = [int(b) for b in bits[:len(a_wires)]]
        bits_b = [int(b) for b in bits[len(a_wires):]]
        a_inputs = {a_wires[i]: (keys[a_wires[i]][bits_a[i]], pbits[a_wires[i]] ^ bits_a[i]) for i in range(len(a_wires))}
        b_inputs = {b_wires[i]: (keys[b_wires[i]][bits_b[i]], pbits[b_wires[i]] ^ bits_b[i]) for i in range(len(b_wires))}
        return a_inputs, b_inputs

    def _print_result(self, bits, a_wires, b_wires, outputs, result):
        str_bits_a = ' '.join(bits[:len(a_wires)])
        str_bits_b = ' '.join(bits[len(a_wires):])
        str_result = ' '.join([str(result[w]) for w in outputs])
        print(f"Alice{a_wires} = {str_bits_a} "
              f"Bob{b_wires} = {str_bits_b}  "
              f"Outputs{outputs} = {str_result}")

    @property
    def print_mode(self):
        return self._print_mode

    @print_mode.setter
    def print_mode(self, print_mode):
        if print_mode not in self.modes:
            logging.error(f"Unknown print mode '{print_mode}', must be in {list(self.modes.keys())}")
            return
        self._print_mode = print_mode
