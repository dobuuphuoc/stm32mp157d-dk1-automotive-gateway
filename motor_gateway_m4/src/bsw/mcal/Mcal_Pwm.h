#ifndef MCAL_PWM_H
#define MCAL_PWM_H

#include "std_types.h"

/* AUTOSAR PWM Types */
typedef uint8 Pwm_ChannelType;

/* Channel Definitions */
#define PWM_CH_MOTOR_ENA    ((Pwm_ChannelType)0u) /* Timer TIM4 CH3 on PD14 (Arduino D10) */
#define PWM_CH_MAX          ((Pwm_ChannelType)1u)

/* PWM Period: 20 kHz = 50,000 ns (FR-M04) */
#define PWM_PERIOD_NS       (50000u)

/* MCAL PWM Service Functions */
Std_ReturnType Mcal_Pwm_Init(void);
Std_ReturnType Pwm_SetDutyCycle(Pwm_ChannelType ChannelNumber, float32 DutyPercent);
void Pwm_SetOutputToIdle(Pwm_ChannelType ChannelNumber);

#endif /* MCAL_PWM_H */
