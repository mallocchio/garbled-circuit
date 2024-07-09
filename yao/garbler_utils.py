import os

ALICE_DATA_PATH = 'input/alice.txt'
BOB_DATA_PATH = 'input/bob.txt'
OUTPUT_FILE_PATH = 'output/result.txt'

def read_input(path):
    """
    Reads the content of a file and returns the data as a list of integers.
    
    :param path: Path of the file to read.
    :return: List of integers from the file.
    :raises ValueError: If the minimum number in the file exceeds 255.
    """
    with open(path, "r", encoding="utf-8") as file:
        input_data = list(map(int, file.readline().split()))

    if min(input_data) >= 255:  # Ensure the input fits within 8 bits
        raise ValueError('The minimum value cannot exceed the maximum value stored in 8 bits (255).')
    
    return input_data

def write_to_file(message='', clear=False):
    """
    Writes a message to a file, appending it to the previous content or clearing the file.
    
    :param message: The message to write.
    :param clear: If True, clears the file before writing.
    """
    with open(OUTPUT_FILE_PATH, 'a', encoding='UTF-8') as file:
        if clear:
            file.truncate(0)
        else:
            file.write(message)

def from_bin_to_decimal(binary_str):
    """
    Converts a binary string to its decimal representation.
    
    :param binary_str: Binary string to convert.
    :return: Decimal representation of the binary string.
    """
    return int(str(binary_str), 2)

def from_decimal_to_bin(decimal_number):
    """
    Converts a decimal number to its binary string representation.
    
    :param decimal_number: The decimal number to convert.
    :return: Binary string representation of the decimal number.
    """
    if decimal_number < 0:
        raise ValueError("The decimal number must be non-negative.")
    return bin(decimal_number)[2:]

def verify_output(result):
        """
        Verifies if the result from the garbled circuit is correct by comparing it to 
        a simple min computed without multiparty computation.
        
        :param result: The min value to verify.
        """
        alice_min = min(read_input(ALICE_DATA_PATH))
        bob_min = min(read_input(BOB_DATA_PATH))
        correct_min = min(alice_min, bob_min)
        
        verification_message = (
            f'\nThe min of the two sets of values is {result} and it is '
            f'{"correct" if correct_min == result else "not correct"}.\n'
        )
        write_to_file(verification_message)