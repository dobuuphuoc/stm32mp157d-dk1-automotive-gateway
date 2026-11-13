#ifndef MCAL_ICU_H
#define MCAL_ICU_H

#include "std_types.h"

/* JGA25-370-46.8K Motor & Optical Encoder Parameters */
#define ICU_ENC_PPR               (11.0f)     /* 11 pulses per motor revolution (single channel) */
#define ICU_ENC_QUAD_MULT         (4.0f)      /* 4x quadrature multiplication (both edges of A and B) */
#define ICU_ENC_GEAR_RATIO        (46.8f)     /* Integrated gearbox reduction ratio 46.8:1 */
#define ICU_ENC_COUNTS_PER_REV    (2059.2f)   /* 11 * 4 * 46.8 counts per output shaft revolution */
#define ICU_SAMPLE_PERIOD_S       (0.01f)     /* 10ms sampling period (100 Hz control loop) */

/* EMA Low-Pass Filter Alpha for speed smoothing (30% raw, 70% filtered) */
#define ICU_RPM_EMA_ALPHA         (0.3f)

/* MCAL ICU Service Functions */
Std_ReturnType Mcal_Icu_Init(void);
void Icu_Update10ms(void);
float32 Icu_GetSpeedRpm(void);
sint32 Icu_GetTotalPulses(void);
void Icu_ResetTotalPulses(void);

#endif /* MCAL_ICU_H */
