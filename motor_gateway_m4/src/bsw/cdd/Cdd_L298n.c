#include "Cdd_L298n.h"
#include "Mcal_Dio.h"
#include "Mcal_Pwm.h"

Std_ReturnType Cdd_L298n_Init(void)
{
    /* Set driver outputs to safe initial state (stopped/coasting) */
    Cdd_L298n_EmergencyStop();
    return E_OK;
}

Std_ReturnType Cdd_L298n_SetCommand(Cdd_L298n_DirType Direction, float32 DutyPercent)
{
    Std_ReturnType status = E_OK;

    switch (Direction) {
    case L298N_DIR_FORWARD:
        Dio_WriteChannel(DIO_CH_L298N_IN1, STD_HIGH);
        Dio_WriteChannel(DIO_CH_L298N_IN2, STD_LOW);
        status = Pwm_SetDutyCycle(PWM_CH_MOTOR_ENA, DutyPercent);
        break;

    case L298N_DIR_REVERSE:
        Dio_WriteChannel(DIO_CH_L298N_IN1, STD_LOW);
        Dio_WriteChannel(DIO_CH_L298N_IN2, STD_HIGH);
        status = Pwm_SetDutyCycle(PWM_CH_MOTOR_ENA, DutyPercent);
        break;

    case L298N_DIR_BRAKE:
        /* Fast motor stop / active braking */
        Dio_WriteChannel(DIO_CH_L298N_IN1, STD_HIGH);
        Dio_WriteChannel(DIO_CH_L298N_IN2, STD_HIGH);
        status = Pwm_SetDutyCycle(PWM_CH_MOTOR_ENA, 0.0f);
        break;

    case L298N_DIR_COAST:
    default:
        /* Free running motor stop / coasting */
        Dio_WriteChannel(DIO_CH_L298N_IN1, STD_LOW);
        Dio_WriteChannel(DIO_CH_L298N_IN2, STD_LOW);
        status = Pwm_SetDutyCycle(PWM_CH_MOTOR_ENA, 0.0f);
        break;
    }

    return status;
}

void Cdd_L298n_EmergencyStop(void)
{
    /* Immediately cut PWM drive to ENA pin */
    Pwm_SetOutputToIdle(PWM_CH_MOTOR_ENA);

    /* Safe state: both direction inputs LOW */
    Dio_WriteChannel(DIO_CH_L298N_IN1, STD_LOW);
    Dio_WriteChannel(DIO_CH_L298N_IN2, STD_LOW);
}
