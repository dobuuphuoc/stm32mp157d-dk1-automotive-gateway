#ifndef STD_TYPES_H
#define STD_TYPES_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* AUTOSAR Standard Fixed-Width Integer & Float Types */
typedef uint8_t         uint8;
typedef uint16_t        uint16;
typedef uint32_t        uint32;
typedef int8_t          sint8;
typedef int16_t         sint16;
typedef int32_t         sint32;
typedef float           float32;
typedef double          float64;

/* AUTOSAR Standard Boolean Type */
typedef bool            boolean;

#ifndef TRUE
#define TRUE            ((boolean)true)
#endif

#ifndef FALSE
#define FALSE           ((boolean)false)
#endif

/* AUTOSAR Standard Return Type */
typedef uint8           Std_ReturnType;
#define E_OK            ((Std_ReturnType)0u)
#define E_NOT_OK        ((Std_ReturnType)1u)

/* AUTOSAR Standard Logic Levels */
#define STD_HIGH        1u
#define STD_LOW         0u

/* Motor Control Operational Modes */
typedef enum {
    MOTOR_MODE_STOPPED     = 0u, /* Motor stopped / coasting (Duty = 0%) */
    MOTOR_MODE_OPEN_LOOP   = 1u, /* Fixed open-loop PWM duty cycle [%] */
    MOTOR_MODE_CLOSED_LOOP = 2u, /* Closed-loop discrete PID speed control [RPM] */
    MOTOR_MODE_STEP_TEST   = 3u, /* Automated open-loop step response for SysID */
    MOTOR_MODE_FAULT       = 4u  /* Emergency stop / active dynamic braking */
} MotorControl_ModeType;

/* Motor Control Step Test Configuration */
typedef struct {
    float32 base_duty;      /* Initial baseline duty cycle [%] before step */
    float32 step_duty;      /* Target step duty cycle [%] during excitation */
    uint32  pre_step_ms;    /* Duration at base_duty before step [ms] */
    uint32  step_dur_ms;    /* Duration at step_duty [ms] */
} MotorControl_StepConfigType;

/* Sensor Data Types for SWC_SensorManager */
typedef struct {
    float32 accel_x_g;      /* GY-61 X-axis acceleration [g] */
    float32 accel_y_g;      /* GY-61 Y-axis acceleration [g] */
    float32 accel_z_g;      /* GY-61 Z-axis acceleration [g] */
    float32 accel_mag_g;    /* Resultant vibration magnitude |a| [g] */
    float32 temperature_c;  /* DHT11 Temperature [degC] */
    float32 humidity_pct;   /* DHT11 Relative Humidity [%] */
    boolean pir_detected;   /* HC-SR501 PIR Motion Detected (TRUE = motion) */
} Sensor_DataType;

/* Safety Fault Reasons for SWC_SafetyManager */
typedef enum {
    SAFETY_OK           = 0u,
    SAFETY_FAULT_PIR    = 1u, /* Obstacle/Human detected in motion zone */
    SAFETY_FAULT_CRASH  = 2u, /* High vibration / collision shock (>2.5g) */
    SAFETY_FAULT_WDG    = 3u, /* IPC Heartbeat Watchdog Timeout (>1.0s) */
    SAFETY_FAULT_MANUAL = 4u  /* Manual E-Stop command from Linux */
} Safety_FaultReasonType;

#endif /* STD_TYPES_H */
