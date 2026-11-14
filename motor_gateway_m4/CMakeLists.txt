cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(motor_gateway_m4)

target_include_directories(app PRIVATE
    src
    src/bsw/mcal
    src/bsw/cdd
    src/rte
    src/asw
)

target_sources(app PRIVATE
    src/main.c
    src/bsw/mcal/Mcal_Dio.c
    src/bsw/mcal/Mcal_Pwm.c
    src/bsw/mcal/Mcal_Adc.c
    src/bsw/mcal/Mcal_Icu.c
    src/bsw/cdd/Cdd_L298n.c
    src/bsw/cdd/Cdd_Ipc.c
    src/bsw/cdd/Cdd_Dht11.c
    src/rte/Rte.c
    src/asw/Swc_MotorControl.c
    src/asw/Swc_SensorManager.c
    src/asw/Swc_SafetyManager.c
)
