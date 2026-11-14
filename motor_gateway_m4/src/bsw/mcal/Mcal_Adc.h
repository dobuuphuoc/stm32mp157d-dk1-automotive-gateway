#ifndef MCAL_ADC_H
#define MCAL_ADC_H

#include "std_types.h"

/* GY-61 (ADXL335) 3-Axis Analog Accelerometer Calibration Constants */
#define MCAL_ADC_RESOLUTION_BITS   12u
#define MCAL_ADC_VREF_VOLTS        3.3f
#define MCAL_ADC_GY61_ZERO_G_VOLTS 1.65f
#define MCAL_ADC_GY61_SENSITIVITY  0.330f   /* 330 mV/g at 3.3V supply */

/* STM32 ADC Channel indices for GY-61 on STM32MP157 */
#define MCAL_ADC_CH_X              14u  /* PF14: Analog Input A4 */
#define MCAL_ADC_CH_Y              13u  /* PF13: Analog Input A3 */
#define MCAL_ADC_CH_Z              12u  /* PF12: Analog Input A5 */

/* MCAL ADC Service Functions */
Std_ReturnType Mcal_Adc_Init(void);
Std_ReturnType Mcal_Adc_ReadGy61(float32 *ax_g, float32 *ay_g, float32 *az_g);

#endif /* MCAL_ADC_H */
