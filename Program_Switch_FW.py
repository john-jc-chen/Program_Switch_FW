import threading
import time
import signal
import sys
import logging
from telnetlib import Telnet

logging.basicConfig(format='%(asctime)s : %(message)s', level=logging.INFO , filename='Running.log')

def check_connectivity(ip):

    logging.info("ping to  {}.".format(ip))
    if sys.platform.lower() == 'win32':
        res = subprocess.run(['ping','-n','3', ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        res = subprocess.run(['ping', '-c', '3', ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode  != 0:
        logging.error("Failed to ping to  {}.".format(ip))
        return False
    else:
        out_text = res.stdout.decode("utf-8", errors='ignore')
        #print(out_text)
        if 'Destination host unreachable' in out_text:
            logging.error("Destination host unreachable at {}.".format(ip))
            return False
        else:
            return True

def read_config_file(config_file):
    data = {}
    try:
        with open(config_file, 'r') as file:
            for line in file:
                result = re.match(r'^(\w+.*?)\:(.*?)$', line)
                if result:
                    value = result.group(2).rstrip().lstrip()
                    if value and value != '':
                        field = result.group(1).rstrip().lstrip()
                        field = re.sub(r'\(.*?\)', '', field)
                        data[field] = value
    except IOError as e:
        print("\nERROR!! config file is not available. Please run this program with config file again. Leave program!")
        #logging.error("config file is not available.")
        sys.exit()
    return data
def run_in_each_slot(config_file, slot):
    data = read_config_file(config_file)

    if "CMM IP" in data.keys():
        CMM_IP = data["CMM IP"]
    if "CMM User Name" in data.keys():
        CMM_name = data["CMM User Name"]
    if "CMM Password" in data.keys():
        CMM_passwd = data["CMM Password"]

    while check_connectivity(CMM_IP):
        com = ['ipmitool.exe', '-I', 'lanplus', '-H', ip, '-U', username, '-P', passwd]
        data = read_config_file(config_file)

        str = slot.upper()




if len(sys.argv) < 2:
    print("Configuration file is missing. Exit!!\n")
    sys.exit(0)
a1 = threading.Thread(target=run_in_each_slot, args=(sys.argv[1], 'a1',))
a2 = threading.Thread(target=run_in_each_slot, args=(sys.argv[1], 'a2',))
b1 = threading.Thread(target=run_in_each_slot, args=(sys.argv[1], 'b1',))
b2 = threading.Thread(target=run_in_each_slot, args=(sys.argv[1], 'b2',))

def run_program():
    a1.setDaemon(True)
    a2.setDaemon(True)
    b1.setDaemon(True)
    b2.setDaemon(True)
    a1.start()
    a2.start()
    b1.start()
    b2.start()
    while True:
        time.sleep(1)

def exit_gracefully(signum, frame):
    # restore the original signal handler as otherwise evil things will happen
    # in raw_input when CTRL+C is pressed, and our signal handler is not re-entrant
    signal.signal(signal.SIGINT, original_sigint)

    try:
        if input("\nReally quit? (y/n)> ").lower().startswith('y'):
            a1.join(0.1)
            a2.join(0.1)
            b1.join(0.1)
            b2.join(0.1)
            sys.exit(1)

    except KeyboardInterrupt:
        print("Ok ok, quitting")
        a1.join(0.1)
        a2.join(0.1)
        b1.join(0.1)
        b2.join(0.1)
        sys.exit(1)

    # restore the exit gracefully handler here
    signal.signal(signal.SIGINT, exit_gracefully)

if __name__ == '__main__':
    # store the original SIGINT handler
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, exit_gracefully)
    run_program()