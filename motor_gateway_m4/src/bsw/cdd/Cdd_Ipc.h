#ifndef CDD_IPC_H
#define CDD_IPC_H

#include "std_types.h"

/* CDD IPC Service Functions */
Std_ReturnType Cdd_Ipc_Init(void);
void Cdd_Ipc_MainFunction_10ms(void);
void Cdd_Ipc_SendFaultNotice(const char *reason);

/* CRC-16-CCITT Calculation Function */
uint16 Cdd_Ipc_CalcCrc16(const uint8 *data, uint16 length);

/* IPC Status Inquiries */
boolean Cdd_Ipc_IsConnected(void);
boolean Cdd_Ipc_IsWatchdogEnabled(void);

#endif /* CDD_IPC_H */
