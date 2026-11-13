#ifndef SWC_MOTOR_CONTROL_H
#define SWC_MOTOR_CONTROL_H

#include "std_types.h"

/* ASW: Software Component Motor Control Functions */
void Swc_MotorControl_Init(void);
void Runnable_MotorControl_10ms(void);

/* Diagnostic & Hardware Verification Interface */
void Swc_MotorControl_SetTestMode(boolean enable, float32 test_duty);
boolean Swc_MotorControl_GetTestMode(void);

#endif /* SWC_MOTOR_CONTROL_H */
