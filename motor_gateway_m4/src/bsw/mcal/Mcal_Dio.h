#ifndef MCAL_DIO_H
#define MCAL_DIO_H

#include "std_types.h"

/* AUTOSAR DIO Types */
typedef uint8 Dio_ChannelType;
typedef uint8 Dio_LevelType;

/* Channel Definitions */
#define DIO_CH_TEST_PE9            ((Dio_ChannelType)0u)  /* PE9: Test Pin for Jitter Measurement (FR-M10) */
#define DIO_CH_L298N_IN1           ((Dio_ChannelType)1u)  /* PE10: L298N Direction IN1 */
#define DIO_CH_L298N_IN2           ((Dio_ChannelType)2u)  /* PH6: L298N Direction IN2 */
#define DIO_CH_STATUS_LED          ((Dio_ChannelType)3u)  /* Board Status LED (led0 alias) */
#define DIO_CH_PIR_PE13            ((Dio_ChannelType)4u)  /* PE13: HC-SR501 PIR Motion Sensor Input */
#define DIO_CH_DHT11_PE12          ((Dio_ChannelType)5u)  /* PE12: DHT11 1-Wire Temperature/Humidity */
#define DIO_CH_MAX                 ((Dio_ChannelType)6u)

/* Output channel count (channels 0..3 are dedicated digital outputs) */
#define DIO_OUTPUT_CHANNEL_COUNT   ((Dio_ChannelType)4u)

/* Pin numbers on GPIOE for hardware fallback when DT spec is unavailable */
#define DIO_PIN_PIR_PE13           (13u)
#define DIO_PIN_DHT11_PE12         (12u)

/* MCAL DIO Service Functions */
Std_ReturnType Mcal_Dio_Init(void);
void Dio_WriteChannel(Dio_ChannelType ChannelId, Dio_LevelType Level);
Dio_LevelType Dio_FlipChannel(Dio_ChannelType ChannelId);
Dio_LevelType Dio_ReadChannel(Dio_ChannelType ChannelId);
Std_ReturnType Dio_SetPinDirection(Dio_ChannelType ChannelId, boolean IsOutput, Dio_LevelType InitialLevel);

#endif /* MCAL_DIO_H */
