#include <zephyr/kernel.h>
#include <zephyr/drivers/adc.h>
#include "Mcal_Adc.h"

#define ZEPHYR_USER_NODE DT_PATH(zephyr_user)

/* Devicetree ADC device binding */
#if DT_NODE_EXISTS(DT_NODELABEL(adc2))
static const struct device *const s_adc_dev = DEVICE_DT_GET(DT_NODELABEL(adc2));
#elif DT_NODE_EXISTS(DT_NODELABEL(adc1))
static const struct device *const s_adc_dev = DEVICE_DT_GET(DT_NODELABEL(adc1));
#else
static const struct device *const s_adc_dev = NULL;
#endif

static volatile boolean s_adc_ready = FALSE;

/* Conversion helper: 12-bit ADC count (0..4095) -> acceleration in g */
static inline float32 Adc_RawToG(int16_t raw_val)
{
    float32 voltage = ((float32)raw_val / 4095.0f) * MCAL_ADC_VREF_VOLTS;
    return (voltage - MCAL_ADC_GY61_ZERO_G_VOLTS) / MCAL_ADC_GY61_SENSITIVITY;
}

Std_ReturnType Mcal_Adc_Init(void)
{
    if (s_adc_dev == NULL || !device_is_ready(s_adc_dev)) {
        s_adc_ready = FALSE;
        return E_NOT_OK;
    }

    /* Configure 12-bit channels for X, Y, Z */
    static const uint8_t channels[] = { MCAL_ADC_CH_X, MCAL_ADC_CH_Y, MCAL_ADC_CH_Z };
    for (size_t i = 0u; i < ARRAY_SIZE(channels); i++) {
        struct adc_channel_cfg ch_cfg = {
            .gain = ADC_GAIN_1,
            .reference = ADC_REF_INTERNAL,
            .acquisition_time = ADC_ACQ_TIME_DEFAULT,
            .channel_id = channels[i],
            .differential = 0
        };
        int ret = adc_channel_setup(s_adc_dev, &ch_cfg);
        if (ret < 0) {
            s_adc_ready = FALSE;
            return E_NOT_OK;
        }
    }

    s_adc_ready = TRUE;
    return E_OK;
}

Std_ReturnType Mcal_Adc_ReadGy61(float32 *ax_g, float32 *ay_g, float32 *az_g)
{
    if (ax_g == NULL || ay_g == NULL || az_g == NULL) {
        return E_NOT_OK;
    }

    if (!s_adc_ready || s_adc_dev == NULL || !device_is_ready(s_adc_dev)) {
        return E_NOT_OK;
    }

    int16_t sample_buffer[1];
    struct adc_sequence sequence = {
        .buffer = sample_buffer,
        .buffer_size = sizeof(sample_buffer),
        .resolution = MCAL_ADC_RESOLUTION_BITS
    };

    /* Read Channel X (PF14) */
    sequence.channels = BIT(MCAL_ADC_CH_X);
    if (adc_read(s_adc_dev, &sequence) != 0) {
        return E_NOT_OK;
    }
    *ax_g = Adc_RawToG(sample_buffer[0]);

    /* Read Channel Y (PF13) */
    sequence.channels = BIT(MCAL_ADC_CH_Y);
    if (adc_read(s_adc_dev, &sequence) != 0) {
        return E_NOT_OK;
    }
    *ay_g = Adc_RawToG(sample_buffer[0]);

    /* Read Channel Z (PF12) */
    sequence.channels = BIT(MCAL_ADC_CH_Z);
    if (adc_read(s_adc_dev, &sequence) != 0) {
        return E_NOT_OK;
    }
    *az_g = Adc_RawToG(sample_buffer[0]);

    return E_OK;
}
