#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>
#include "Mcal_Dio.h"

#define ZEPHYR_USER_NODE DT_PATH(zephyr_user)

/* Devicetree GPIO specifications */
#if DT_NODE_EXISTS(ZEPHYR_USER_NODE)
static const struct gpio_dt_spec s_dio_test = GPIO_DT_SPEC_GET_OR(ZEPHYR_USER_NODE, test_gpios, {0});
static const struct gpio_dt_spec s_dio_in1  = GPIO_DT_SPEC_GET_OR(ZEPHYR_USER_NODE, in1_gpios, {0});
static const struct gpio_dt_spec s_dio_in2  = GPIO_DT_SPEC_GET_OR(ZEPHYR_USER_NODE, in2_gpios, {0});
#else
static const struct gpio_dt_spec s_dio_test = {0};
static const struct gpio_dt_spec s_dio_in1  = {0};
static const struct gpio_dt_spec s_dio_in2  = {0};
#endif

#if DT_NODE_EXISTS(DT_ALIAS(led0))
static const struct gpio_dt_spec s_dio_led = GPIO_DT_SPEC_GET_OR(DT_ALIAS(led0), gpios, {0});
#else
static const struct gpio_dt_spec s_dio_led = {0};
#endif

/* Direct GPIOE device binding for PE12 (DHT11) and PE13 (PIR) */
#if DT_NODE_EXISTS(DT_NODELABEL(gpioe))
static const struct device *const s_gpioe_dev = DEVICE_DT_GET(DT_NODELABEL(gpioe));
#else
static const struct device *const s_gpioe_dev = NULL;
#endif

/* Cache channel output levels */
static Dio_LevelType s_dio_levels[DIO_CH_MAX] = {STD_LOW, STD_LOW, STD_LOW, STD_LOW, STD_LOW, STD_LOW};

static const struct gpio_dt_spec *Mcal_Dio_GetSpec(Dio_ChannelType ChannelId)
{
    switch (ChannelId) {
    case DIO_CH_TEST_PE9:
        return &s_dio_test;
    case DIO_CH_L298N_IN1:
        return &s_dio_in1;
    case DIO_CH_L298N_IN2:
        return &s_dio_in2;
    case DIO_CH_STATUS_LED:
        return &s_dio_led;
    default:
        return NULL;
    }
}

Std_ReturnType Mcal_Dio_Init(void)
{
    Std_ReturnType status = E_OK;

    /* Initialize output channels (PE9, PE10, PH6, LED) */
    for (Dio_ChannelType ch = 0; ch < 4u; ch++) {
        const struct gpio_dt_spec *spec = Mcal_Dio_GetSpec(ch);
        if (spec != NULL && spec->port != NULL && gpio_is_ready_dt(spec)) {
            int ret = gpio_pin_configure_dt(spec, GPIO_OUTPUT_INACTIVE);
            if (ret < 0) {
                status = E_NOT_OK;
            }
            s_dio_levels[ch] = STD_LOW;
        }
    }

    /* Initialize input channels on GPIOE: PE13 (PIR Motion) & PE12 (DHT11) */
    if (s_gpioe_dev != NULL && device_is_ready(s_gpioe_dev)) {
        /* PE13: Pulldown input (HC-SR501 outputs 3.3V HIGH on motion detection) */
        int ret_pir = gpio_pin_configure(s_gpioe_dev, 13, GPIO_INPUT | GPIO_PULL_DOWN);
        if (ret_pir < 0) {
            status = E_NOT_OK;
        }
        /* PE12: Pullup input (DHT11 1-wire line idle HIGH) */
        int ret_dht = gpio_pin_configure(s_gpioe_dev, 12, GPIO_INPUT | GPIO_PULL_UP);
        if (ret_dht < 0) {
            status = E_NOT_OK;
        }
    }

    return status;
}

void Dio_WriteChannel(Dio_ChannelType ChannelId, Dio_LevelType Level)
{
    if (ChannelId >= 4u) {
        return; /* Only channels 0-3 are writable outputs */
    }

    const struct gpio_dt_spec *spec = Mcal_Dio_GetSpec(ChannelId);
    if (spec != NULL && spec->port != NULL && gpio_is_ready_dt(spec)) {
        int val = (Level == STD_HIGH) ? 1 : 0;
        gpio_pin_set_dt(spec, val);
        s_dio_levels[ChannelId] = (Level == STD_HIGH) ? STD_HIGH : STD_LOW;
    }
}

Dio_LevelType Dio_FlipChannel(Dio_ChannelType ChannelId)
{
    if (ChannelId >= 4u) {
        return STD_LOW; /* Only channels 0-3 are flippable */
    }

    const struct gpio_dt_spec *spec = Mcal_Dio_GetSpec(ChannelId);
    if (spec != NULL && spec->port != NULL && gpio_is_ready_dt(spec)) {
        gpio_pin_toggle_dt(spec);
        s_dio_levels[ChannelId] = (s_dio_levels[ChannelId] == STD_HIGH) ? STD_LOW : STD_HIGH;
        return s_dio_levels[ChannelId];
    }

    return STD_LOW;
}

Dio_LevelType Dio_ReadChannel(Dio_ChannelType ChannelId)
{
    if (ChannelId == DIO_CH_PIR_PE13) {
        if (s_gpioe_dev != NULL && device_is_ready(s_gpioe_dev)) {
            return (gpio_pin_get(s_gpioe_dev, 13) > 0) ? STD_HIGH : STD_LOW;
        }
    } else if (ChannelId == DIO_CH_DHT11_PE12) {
        if (s_gpioe_dev != NULL && device_is_ready(s_gpioe_dev)) {
            return (gpio_pin_get(s_gpioe_dev, 12) > 0) ? STD_HIGH : STD_LOW;
        }
    } else if (ChannelId < 4u) {
        return s_dio_levels[ChannelId];
    }

    return STD_LOW;
}
