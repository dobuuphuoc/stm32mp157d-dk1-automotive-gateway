#ifndef RTE_H
#define RTE_H

#include "std_types.h"

/* RTE Lifecycle & Scheduling */
void Rte_Init(void);
void Rte_TimerEvent_10ms(void);

/* RTE Sender-Receiver & Mode Ports: Motor Control Data Flow */
Std_ReturnType Rte_Read_rpMotorMode(MotorControl_ModeType *mode);
Std_ReturnType Rte_Write_ppMotorMode(MotorControl_ModeType mode);
Std_ReturnType Rte_Read_rpSpeed_rpm(float32 *speed);
Std_ReturnType Rte_Write_ppDuty_percentage(float32 duty);
Std_ReturnType Rte_Read_rpTargetSpeed_rpm(float32 *target_rpm);
Std_ReturnType Rte_Write_ppTargetSpeed_rpm(float32 target_rpm);
Std_ReturnType Rte_Read_rpTargetDuty_percentage(float32 *target_duty);
Std_ReturnType Rte_Write_ppTargetDuty_percentage(float32 target_duty);
Std_ReturnType Rte_Read_rpStepConfig(MotorControl_StepConfigType *config);
Std_ReturnType Rte_Write_ppStepConfig(const MotorControl_StepConfigType *config);
Std_ReturnType Rte_Read_rpEmergencyStop(boolean *estop);
Std_ReturnType Rte_Write_ppEmergencyStop(boolean estop);

/* RTE Sender-Receiver Ports: Sensor & Safety Management Data Flow */
Std_ReturnType Rte_Read_rpSensorData(Sensor_DataType *data);
Std_ReturnType Rte_Write_ppSensorData(const Sensor_DataType *data);
Std_ReturnType Rte_Read_rpSafetyFault(Safety_FaultReasonType *fault);
Std_ReturnType Rte_Write_ppSafetyFault(Safety_FaultReasonType fault);

/* RTE BSW-side accessor functions */
MotorControl_ModeType Rte_Get_MotorMode(void);
void Rte_Set_MotorMode(MotorControl_ModeType mode);
const char *Rte_Get_MotorModeString(MotorControl_ModeType mode);
float32 Rte_Get_ppDuty_percentage(void);
void Rte_Set_rpSpeed_rpm(float32 speed);
float32 Rte_Get_rpSpeed_rpm(void);
float32 Rte_Get_ppTargetSpeed_rpm(void);
void Rte_Set_rpTargetSpeed_rpm(float32 target_rpm);
float32 Rte_Get_TargetDuty_percentage(void);
void Rte_Set_TargetDuty_percentage(float32 target_duty);
void Rte_Get_StepConfig(MotorControl_StepConfigType *config);
void Rte_Set_StepConfig(const MotorControl_StepConfigType *config);
boolean Rte_Get_EmergencyStop(void);
void Rte_Set_EmergencyStop(boolean estop);
void Rte_Get_SensorData(Sensor_DataType *data);
Safety_FaultReasonType Rte_Get_SafetyFault(void);

/* RTE Client-Server ports: sensor drivers */
Std_ReturnType Rte_Call_rpEnvSensor_Read(float32 *temp_c, float32 *hum_pct);
Std_ReturnType Rte_Call_rpAccel_Read(float32 *ax_g, float32 *ay_g, float32 *az_g);
void Rte_Get_Dht11Stats(uint32 *ok_cnt, uint32 *err_cnt);

#endif /* RTE_H */
