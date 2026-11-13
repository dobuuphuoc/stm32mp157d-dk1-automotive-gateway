#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include "std_types.h"
#include "Mcal_Dio.h"
#include "Mcal_Pwm.h"
#include "Mcal_Icu.h"
#include "Cdd_L298n.h"
#include "Cdd_Ipc.h"
#include "Swc_MotorControl.h"
#include "Rte.h"

/* High priority deterministic 10ms timer and synchronization semaphore */
static struct k_timer s_timer_10ms;
static struct k_sem s_sem_10ms;

static void Timer10ms_ExpiryCallback(struct k_timer *timer_id)
{
    ARG_UNUSED(timer_id);
    k_sem_give(&s_sem_10ms);
}

void EcuM_Init(void)
{
    printk("[EcuM] Starting ECU State Manager...\n");

    /* Initialize Microcontroller Abstraction Layer (MCAL) */
    if (Mcal_Dio_Init() != E_OK) {
        printk("[EcuM] MCAL Dio Init failed!\n");
    } else {
        printk("[EcuM] MCAL Dio Initialized.\n");
    }

    if (Mcal_Pwm_Init() != E_OK) {
        printk("[EcuM] MCAL Pwm Init failed!\n");
    } else {
        printk("[EcuM] MCAL Pwm Initialized.\n");
    }

    if (Mcal_Icu_Init() != E_OK) {
        printk("[EcuM] MCAL Icu Init failed!\n");
    } else {
        printk("[EcuM] MCAL Icu Initialized.\n");
    }

    /* Initialize Complex Device Drivers (CDD) */
    if (Cdd_L298n_Init() != E_OK) {
        printk("[EcuM] CDD L298N Init failed!\n");
    } else {
        printk("[EcuM] CDD L298N Initialized.\n");
    }

    if (Cdd_Ipc_Init() != E_OK) {
        printk("[EcuM] CDD IPC Init failed!\n");
    } else {
        printk("[EcuM] CDD IPC Initialized.\n");
    }

    /* Initialize Application Software Components */
    Swc_MotorControl_Init();
    printk("[EcuM] SWC MotorControl Initialized.\n");

    /* Initialize Runtime Environment */
    Rte_Init();
    printk("[EcuM] RTE Initialized.\n");

    printk("[EcuM] State transition: RUN\n");
}

int main(void)
{
    printk("=============================================\n");
    printk("STM32MP157 Motor Gateway - Cortex-M4 Firmware\n");
    printk("AUTOSAR Classic Architecture on Zephyr RTOS\n");
    printk("=============================================\n");

    /* Initialize ECU state */
    EcuM_Init();

    /* Raise thread priority to preemptive priority 1 for minimal scheduling latency */
    k_thread_priority_set(k_current_get(), K_PRIO_PREEMPT(1));

    /* Initialize deterministic periodic timer and semaphore */
    k_sem_init(&s_sem_10ms, 0, 1);
    k_timer_init(&s_timer_10ms, Timer10ms_ExpiryCallback, NULL);
    k_timer_start(&s_timer_10ms, K_MSEC(10), K_MSEC(10));

    printk("[Main] Periodic 10ms control loop active (Timer/Sem).\n");

    /* High-priority deterministic cyclic execution */
    while (1) {
        if (k_sem_take(&s_sem_10ms, K_FOREVER) == 0) {
            Rte_TimerEvent_10ms();
        }
    }

    return 0;
}
