import threading
import time
import signal
import sys
import logging
import re
import subprocess
from telnetlib import Telnet

logging.basicConfig(format='%(asctime)s : %(message)s', level=logging.INFO , filename='Running.log')

global_lock = threading.Lock()

def update_config(config_file, slot):
    while global_lock.locked():
        continue

    global_lock.acquire()
    data = []
    with open(config_file, "r") as file:
        for line in file:
            result = re.match(r'^\s?' + slot.upper() + '(\s+\w+\:).*$', line)
            if result:
                line = slot.upper() + result.group(1) + "\n"
            data.append(line)

    with open(config_file, "w") as file:
        for line in data:
            #print(line)
            file.write(line)
    global_lock.release()

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

def telnet_to_switch(ip, name, password,tftp, file):

    tn = Telnet(ip)
    tn.read_until(b"login:")
    tn.write(name.encode('utf-8') + b"\r\n")
    tn.read_until(b"Password:")
    tn.write(password.encode('utf-8') + b"\r\n")
    tn.read_until(b"#")
    command = 'firmware upgrade tftp://' + tftp + '/' + file + ' normal'
    tn.write(command.encode('utf-8') + b"\r\n")
    msg = tn.read_until(b"#", timeout=2.0).decode('utf-8', errors='ignore')
    Fail = True
    logging.info("Programming FW normal on {}. ".format(ip))
    while "#" not in msg:
        #print(msg)
        msg = tn.read_until(b"#", timeout=5.0).decode('utf-8', errors='ignore')
        if 'successfully' in msg:
            Fail = False
        if '[y/n]' in msg:
            tn.write('y'.encode('utf-8'))
    #print(msg)
    if Fail:
        return False
    logging.info("Programming FW fallback on {}. ".format(ip))
    #print(msg)
    command = 'firmware upgrade tftp://' + tftp + '/' + file + ' fallback'
    tn.write(command.encode('utf-8') + b"\r\n")
    msg = tn.read_until(b"#", timeout=2.0).decode('utf-8', errors='ignore')
    Fail = True
    while "#" not in msg:
        #print(msg)
        msg = tn.read_until(b"#", timeout=5.0).decode('utf-8', errors='ignore')
        if 'successfully' in msg:
            Fail = False
        if '[y/n]' in msg:
            tn.write('y'.encode('utf-8'))
    #print(msg)
    if Fail:
        return False
    logging.info("reload on {}. ".format(ip))
    tn.write('reload'.encode('utf-8') + b"\r\n")
    msg = tn.read_until(b"#", timeout=2.0).decode('utf-8', errors='ignore')
    while "#" not in msg:
        #print(msg)
        if '[y/n]' in msg:
            tn.write('y'.encode('utf-8'))
            break
        msg = tn.read_until(b"#", timeout=3.0).decode('utf-8', errors='ignore')
    #print('Restarting\n')
    #time.sleep(135.0)
    while not check_connectivity(ip):
        time.sleep(5.0)
    logging.info("Re-connect to  on {}. ".format(ip))
    tn = Telnet(ip)
    tn.read_until(b"login:")
    tn.write(name.encode('utf-8') + b"\r\n")
    tn.read_until(b"Password:")
    tn.write(password.encode('utf-8') + b"\r\n")
    tn.read_until(b"#")
    tn.write('show version'.encode('utf-8') + b"\r\n")
    print(tn.read_until(b"#", timeout=2.0).decode('utf-8', errors='ignore'))

    return True

def run_in_each_slot(config_file, slot):
    data = read_config_file(config_file)

    if "CMM IP" in data.keys():
        CMM_IP = data["CMM IP"]
    if "CMM User Name" in data.keys():
        CMM_name = data["CMM User Name"]
    if "CMM Password" in data.keys():
        CMM_passwd = data["CMM Password"]
    if "TFTP IP" in data.keys():
        tftp = data["TFTP IP"]
    if "Firmware File Name":
        file_name = data["Firmware File Name"]
    #print("{} {} {} {} {}".format(CMM_IP,CMM_name, CMM_passwd, tftp, file_name))
    if check_connectivity(CMM_IP):
        com = ['tool\ipmitool.exe', '-I', 'lanplus', '-H', CMM_IP, '-U', CMM_name, '-P', CMM_passwd]
        Current_IP = 0
        while True:
            try:
                output = subprocess.run(com + ['raw', '0x30', '0x33', '0x0b', '0x' + slot], stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
            except Exception as e:
                print("ERROR!! Error has occurred in read data from CMM. Skip programming {}}.\n".format(slot))
                logging.error("ERROR!! Error has occurred in reading {} IP. ".format(slot) + str(e))
            #print(output)
            if output.returncode == 0:
                ip_text_ary = output.stdout.decode("utf-8", errors='ignore').split()[1:]
                #print(ip_text_ary)
                ip = ''
                for i in ip_text_ary:
                    ip = ip + str(int(i, 16)) + '.'
                ip = ip.rstrip(".")
                #print('ip is {}'.format(ip))

                if Current_IP != ip:
                    Current_IP = ip
                else:
                    continue
                if Current_IP == '0.0.0.0':
                    continue
                print("Connecting to {} in {}".format(ip, slot))
                if check_connectivity(ip):
                    data = read_config_file(config_file)
                    # if slot.upper() + " User Name" in data.keys():
                    #     name = data[slot.upper() + " User Name"]
                    logging.info("Check connectivity to {} is ok in {}. ".format(ip, slot))
                    if slot.upper() + " Password" in data.keys():
                        password = data[slot.upper() + " Password"]
                        #print('password is {}'.format(password))
                        print("Programming FW in {}".format(slot))
                        if telnet_to_switch(ip, 'ADMIN', password, tftp, file_name):
                            print('Finished in {}'.format(slot))
                            logging.info('Finished in {}'.format(slot))
                            update_config(config_file, slot)
                        else:
                            print('ERROR!! Failed in {}'.format(slot))
                else:
                    print('Can NOT connect to switch in ' + slot.upper() + ' . Skip programming this slot.')
            time.sleep(10.0)

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
        pass

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