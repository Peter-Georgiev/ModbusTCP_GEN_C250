#! /usr/bin/python3
import time
import sys
import logging
from pymodbus.client import ModbusTcpClient
# За modbus 2.5 pymodbus.client.sync, а за >=3.0 pymodbus.client

# Конфигуриране на логера
ENCODING = 'utf-8'
LOG_FILE = 'log_generator_c250.log'
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding=ENCODING #За python 3.6 да се коментира
    )
logger = logging.getLogger(__name__)
print("\n")
logging.info("Програмата е стартирана.")

# Настройки за връзката
IP_ADDRESS = '192.168.110.40'  # IP адрес на устройството
PORT = 502                     # Порт за Modbus (по подразбиране 502)
SLAVE_ID = 3                   # Адрес на устройството (Modbus адрес 3)
REGISTER_COUNT = 1             # Брой регистри за четене

#Genset State: 0-Ready, 1-Precrank, 2-Ramp, 3-Running
GEN_STATE_READY = 0
GEN_STATE_PRECRANK = 1
GEN_STATE_RAMP = 2
GEN_STATE_RUNNING = 3

# Адреси на регистри
REGISTERS = {
    'switch_position': 10,      # Адрес на регистъра 10 - Operation Mode Switch Position (Read Only)
    'genset_state': 11,         # Адрес на регистъра 11 - Genset State (Read Only)
    'active_fault_code': 12,    # Адрес на регистъра 12 - Active Fault (Read Only)
    'active_fault_type': 13,    # Адрес на регистъра 13 - Active Fault (Read Only)
    'l1_n_vol': 18,             # Адрес на регистъра 18 - Alternator L1-N Voltage (Read Only)
    'l2_n_vol': 19,             # Адрес на регистъра 19 - Alternator L2-N Voltage (Read Only)
    'l3_n_vol': 20,             # Адрес на регистъра 20 - Alternator L3-N Voltage (Read Only)
    'l1_current': 26,           # Адрес на регистъра 26 - Alternator L1 Current (Read Only)
    'l2_current': 27,           # Адрес на регистъра 27 - Alternator L2 Current (Read Only)
    'l3_current': 28,           # Адрес на регистъра 27 - Alternator L3 Current (Read Only)
    'average_current': 29,      # Адрес на регистъра 29 - Alternator Average Current (Read Only)
    'out_va_total': 43,         # Адрес на регистъра 43 - Alternator Output VA Total (Read Only)
    'alt_frequency': 44,        # Адрес на регистъра 44 - Average Alternator Line Frequency (Read Only)
    'battery_voltage': 61,      # Адрес на регистъра 61 - Battery Voltage (Read Only)
    'oil_pressure': 62,         # Monitor point for oil pressure
    'coolant_temp': 64,         # Адрес на регистъра 64 - Coolant Temperature (Read Only)
    'engine_speed': 68,         # Адрес на регистъра 68 - Engine Speed (Read Only)
    'modbus_start_stop': 300,   # Адрес на регистъра 300 - Genset start stop control via Modbus (Read and Write)
    'fault_reset_modbus': 301,  # Адрес на регистъра 301 - Fault reset via Modbus (No logical) (Read and Write)
    'e_stop_switch_modbus': 302,# Адрес на регистъра 302 - Genset Estop switch via Modbus (No logical) (Read and Write)
    'start_time_delay': 3006,   # Адрес на регистъра 3006 - Start Time Delay (Read and Write)
    'stop_time_delay': 3007     # Адрес на регистъра 3007 - Stop Time Delay (Read and Write)
}

# Пренасочване на стандартния изход към лог файл и терминала
class StdoutRedirector:
    def __init__(self):
        self.terminal = sys.stdout  # Оригиналният изход на терминала
        # Отваряме лог файла за добавяне на нови записи
        self.log_file = open(LOG_FILE, "a",  encoding=ENCODING)

    def write(self, message):
        self.terminal.write(message)  # Разпечатваме на терминала
        self.log_file.write(message)  # Записваме в лог файла

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

# Пренасочваме stdout към нашия нов обект
sys.stdout = StdoutRedirector()

# Пренасочване на входа (това, което се въвежда от клавиатурата)
class StdinRedirector:
    def __init__(self):
        self.terminal = sys.stdin  # Оригиналният изход за вход от терминала

    def read(self):
        return self.terminal.read()  # Прочитаме целия вход

    def readline(self):
        user_input = self.terminal.readline()  # Прочитаме ред по ред от входа
        logger.info(f"Потребителски вход: {user_input.strip()}")  # Логваме входа
        return user_input  # Връщаме прочетеното

# Пренасочваме stdin към нашия нов обект
sys.stdin = StdinRedirector()

# Създаване на Modbus TCP връзка
client = ModbusTcpClient(host=IP_ADDRESS, port=PORT)
if not client.connect():
    exit("Неуспешно свързване с ModbusTCP устройството.")
print("Свързан успешно с ModbusTCP устройството.")

# Функции за четене по Modbus
def read_register(address, count=REGISTER_COUNT, slave_id=SLAVE_ID):
    response = client.read_holding_registers(address=address - 1, count=count, slave=slave_id)
    # За modbus (>=3.0 slave=slave_id, а за 2.5 unit=slave_id)
    if response.isError():
        raise ValueError(f"Грешка при четене от регистър {address}: {response}")
    return response.registers

# Функции за запис по Modbus
def write_register(address, value, slave_id=SLAVE_ID):
    response = client.write_register(address=address - 1, value=value, slave=slave_id)
    # За modbus (>=3.0 slave=slave_id, а за 2.5 unit=slave_id)
    if response.isError():
        raise ValueError(f"Грешка при запис в регистър {address}: {response}")
    return response

#Messages: 11 - Genset State
def state_genset_state(value):
    states = {
        0: "READY: Генератора е в готовност.",
        1: "PRECRANK: Генератора подготвя запалване.",
        2: "RAMP: Генератора се ускорява.",
        3: "RUNNING: Генератора работи."
    }
    return states.get(value, f"UNKNOWN: Неизвестна стойност = {value}.")

#Messages: 10 - Operation Mode Switch Position
def state_switch_position(value):
    positions = {
        0: "Off: Генераторът е изключен.",
        1: "Auto: Генераторът е в автоматичен режим.",
        2: "Manual: Генераторът е в ръчен режим."
    }
    return positions.get(value, f"UNKNOWN: Неизвестна стойност = {value}.")
 
 #Messages: 13 - Active Fault Type
def state_fault_type(value):
    fault_types = {
        0: "NORMAL:",
        1: "WARNING:",
        4: "SHUTDOWN:"
    }
    return fault_types.get(value, "UNKNOWN:")

#Messages: 12 - Active Fault Code
def state_fault_code(code, fault_type):
    faults = {
        0: f"CODE - {code} Няма грешки.",
        1: f"CODE - {code} HIGH COOLANT TEMPERATURE.",
        12: f"CODE - {code} HIGH AC VOLTAGE.",
        13: f"CODE - {code} LOW AC VOLTAGE.",
        61: f"CODE - {code} EMERGENCY STOP.",
        73: f"CODE - {code} FAIL TO START.",
        203: f"CODE - {code} LOW COOLANT TEMPERATURE.",
        213: f"CODE - {code} LOW BATTERY.",
        214: f"CODE - {code} HIGH BATTERY."
    }
    fault_message = faults.get(code, f"Неизвестна грешка (CODE: {code}).")
    return f"{state_fault_type(fault_type)} {fault_message}"

#Messages: Active Fault code + Active Fault Type 
def active_fault():
    #12 - Active Fault Code
    active_fault_code = read_register(REGISTERS['active_fault_code'])[0]
    #13 - Active Fault Type
    active_fault_type = read_register(REGISTERS['active_fault_type'])[0]

    return state_fault_code(active_fault_code, active_fault_type)

# Потвърждение с (y/n) на въведената стойност
def input_confirm(action):
    confirmation = input(f"Въведената стойност е: {action}. Потвърждавате ли? (y/n): ").strip().lower()
    if confirmation != 'y':
        return False
    return True

# Функция за въвеждане на номер от менюто
def get_input_value(input_num, value_0, value_1):    
    try:
        action = int(input(f"Въведете команда за вход {input_num}: 0 - {value_0}, 1 - {value_1}: "))
        if action not in [0, 1]:
            raise ValueError("Невалидна стойност! Въведете 0 или 1.")
        return action            
    except ValueError as e:
        print(f"Грешка: {e}")

#Принтиране на стойностите на акумулатора (Vdc) и антефриз (°C)
def print_common_gen_info(battery_voltage, coolant_temp):
    print(f"Акумулатор: {battery_voltage:.2f} Vdc.")
    print(f"Температура на антефриз: {coolant_temp:.2f} °C.")

#1. Прочетете статус на генератора.
def choice_1_gen_status():
    #11 - Genset State: 0-Ready, 1-Precrank, 2-Ramp, 3-Running
    state = read_register(REGISTERS['genset_state'])[0]
    print(state_genset_state(state))

    #10 - Operation Mode Switch Position
    msg_switch_position = state_switch_position(read_register(REGISTERS['switch_position'])[0])
    #61 - Battery Voltage
    result_battery_voltage = read_register(REGISTERS['battery_voltage'])[0] *0.1
    #62 - Oil Pressure
    result_oil_pressure = read_register(REGISTERS['oil_pressure'])[0]
    #64 - Coolant Temperature
    result_coolant_temp = read_register(REGISTERS['coolant_temp'])[0] * 0.1
    #68 - Engine Speed
    result_engine_spee = read_register(REGISTERS['engine_speed'])[0]
    #300 - Genset start stop control via Modbus: 0-START, 1-STOP (Read and Write)
    modbus_start_stop = read_register(REGISTERS['modbus_start_stop'])[0]
        
    #Messages Active Fault Type
    msg_active_fault = active_fault()
        
    print(f"Operation Mode Switch Position: {msg_switch_position}")
    print(f"Active Fault: {msg_active_fault}")
    print(f"Engine Speed = {result_engine_spee} Rpm.")
    print(f"Oil Pressure = {result_oil_pressure} kPa.")

    if state == GEN_STATE_READY:
        print(f"{state_genset_state(state)}")

        if modbus_start_stop == 1:
            #3006 - Start Time Delay
            start_time_delay = read_register(REGISTERS['start_time_delay'])[0]            
            print(f"Изчакваме - (Start Time Delay: {start_time_delay} sec.).")
            print(f"Изпратена команда за СТАРТИРАНЕ на генератора по mobdus!")
            time.sleep(3)

        print_common_gen_info(result_battery_voltage, result_coolant_temp)

    elif state == GEN_STATE_PRECRANK:
        print(f"{state_genset_state(state)}")
        
        if modbus_start_stop == 1:
            print(f"Изпратена команда за СТАРТИРАНЕ на генератора по mobdus!")
        elif modbus_start_stop == 0:
            print(f"Възможно дa е изпратена команда за СПИРАНЕ на генератора по mobdus!")

        print_common_gen_info(result_battery_voltage, result_coolant_temp)
    elif state == GEN_STATE_RAMP:
        print(f"{state_genset_state(state)}")

        if modbus_start_stop == 1:
            print(f"Изпратена команда за СТАРТИРАНЕ на генератора по mobdus!")
        elif modbus_start_stop == 0:
            print(f"Възможно да е команда за СПИРАНЕ на генератора по mobdus!")

        print_common_gen_info(result_battery_voltage, result_coolant_temp)
    elif state == GEN_STATE_RUNNING:
        print(f"{state_genset_state(state)}")

        l1_n_vol = read_register(REGISTERS['l1_n_vol'])[0]
        l2_n_vol = read_register(REGISTERS['l2_n_vol'])[0]
        l3_n_vol = read_register(REGISTERS['l3_n_vol'])[0]  
        l1_current = read_register(REGISTERS['l1_current'])[0] * 0.1
        l2_current = read_register(REGISTERS['l2_current'])[0] * 0.1
        l3_current = read_register(REGISTERS['l3_current'])[0] * 0.1
        average_current = read_register(REGISTERS['average_current'])[0] * 0.1
        alt_frequency = read_register(REGISTERS['alt_frequency'])[0] * 0.1
        out_va_total = read_register(REGISTERS['out_va_total'])[0]

        if modbus_start_stop == 0:
            #3007 - Stop Time Delay
            stop_time_delay = read_register(REGISTERS['stop_time_delay'])[0]
            print(f"Stop Time Delay: {stop_time_delay} sec.")
        if modbus_start_stop == 1:
            print(f"Генератора е стартиран по Modbus!")

        print(f"Genset start stop control via Modbus: регистър:{REGISTERS['modbus_start_stop']}, стойност:{modbus_start_stop}")
        print_common_gen_info(result_battery_voltage, result_coolant_temp)        
        print(f"Alternator L1-N = {l1_n_vol} Vac.")
        print(f"Alternator L2-N = {l2_n_vol} Vac.")
        print(f"Alternator L3-N = {l3_n_vol} Vac.")
        print(f"Alternator L1 Current = {l1_current:.2f} Amp.")
        print(f"Alternator L2 Current = {l2_current:.2f} Amp.")
        print(f"Alternator L3 Current = {l3_current:.2f} Amp.")
        print(f"Alternator Average Current = {average_current:.2f} Amp.")
        print(f"Alternator Output VA Total = {out_va_total} kVa.")
        print(f"Average Alternator Line Frequency = {alt_frequency:.2f} Hz.")        
    else:
        print(f"{state_genset_state(state)}")

# Показване на меню
def show_menu():
    print("\nМеню - Genset C250:")
    print("1. Прочетете статус на генератора.")
    print("2. Стартиране/Спиране на генератора.")
    print("3. Аварийно спиране (E-Stop).")
    print("4. Изход от програмата.")

# Основна програма
def main():
    while True:
        show_menu()
        choice = input("Изберете опция (1-4): ").strip()
        print("\n------------------------------------------------------------------------------")

        if choice == '1':
            #1. Прочетете статус на генератора.
            try:            
                choice_1_gen_status()
            except ValueError as e:
                print(e)

        elif choice == '2':
            #2. Стартиране/Спиране на генератора.
            try:
                # Генератор - СТАРТ/СТОП през Modbus.
                action = get_input_value(2, "СТОП", "СТАРТ")
                isAction = input_confirm(action)
                
                if not isAction and action == 0:
                    print("Операцията СТОП през Modbus е отказана.")
                    continue
                elif not isAction and action == 1:
                    print("Операцията СТАРТ през Modbus е отказана.")
                    continue

                write_register(REGISTERS['modbus_start_stop'], action)
                print(f"Успешно записана стойност: {action} в регистър: {REGISTERS['modbus_start_stop']}.")                
                                    
                if action == 0:
                    #3007 - Stop Time Delay
                    stop_time_delay = read_register(REGISTERS['stop_time_delay'])[0]
                    print(f"Изпратена е команда за СПИРАНЕ!!! (Stop Time Delay: {stop_time_delay} sec.).")
                    #Genset State: 0-Ready, 1-Precrank, 2-Ramp, 3-Running
                    state = read_register(REGISTERS['genset_state'])[0]
                    print(f"{state_genset_state(state)}")
                
                elif action == 1:
                    #3006 - Start Time Delay
                    start_time_delay = read_register(REGISTERS['start_time_delay'])[0]
                    print(f"Изпратена команда за СТАРТИРАНЕ! (Start Time Delay: {start_time_delay} sec.).")
                    print(f"Изчакваме 10 секунди да запали двигателя.")

                    time.sleep(10)
                    #Genset State: 0-Ready, 1-Precrank, 2-Ramp, 3-Running
                    state = read_register(REGISTERS['genset_state'])[0]
                    print(f"{state_genset_state(state)}")       

                #Messages Active Fault Type
                time.sleep(3)
                msg_active_fault = active_fault()
                print(f"{msg_active_fault}")                
            except ValueError as e:
                print(e)
        elif choice == '3':
            try:
                # Генератор - Estop switch през Modbus.            
                action = get_input_value(3, "E-Stop Inactive", "E-Stop Active")
                isAction = input_confirm(action)
                if not isAction:
                    print("Операцията Estop switch през Modbus е отказана.")
                    continue

                write_register(REGISTERS['e_stop_switch_modbus'], action)

                print(f"Командата за аварийно спиране е изпратена успешно: {action}")
                print(f"Успешно записана стойност: {action} в регистър: {REGISTERS['e_stop_switch_modbus']}.")

                return_e_stop_switch_modbus = read_register(REGISTERS['e_stop_switch_modbus'])[0]
                if return_e_stop_switch_modbus == 0:
                    print(f"E-STOP Inactive")
                elif return_e_stop_switch_modbus == 1:
                    print(f"E-STOP Active")

                #Messages Active Fault Type
                time.sleep(3)
                msg_active_fault = active_fault()
                print(f"{msg_active_fault}")
            except ValueError as e:
                print(e)
        elif choice == '4':
            client.close()
            print("Изход от програмата.\n")
            break

        else:
            print("Невалиден избор. Опитайте отново.")

if __name__ == "__main__":
    main()