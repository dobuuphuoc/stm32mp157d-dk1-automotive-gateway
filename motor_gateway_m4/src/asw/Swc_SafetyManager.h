#ifndef SWC_SAFETY_MANAGER_H
#define SWC_SAFETY_MANAGER_H

#include "std_types.h"

void Swc_SafetyManager_Init(void);
void Runnable_SafetyCheck_10ms(void);
void Swc_SafetyManager_ClearFault(void);
void Swc_SafetyManager_SetPirEnable(boolean enable);
Safety_FaultReasonType Swc_SafetyManager_GetFault(void);
const char *Swc_SafetyManager_GetFaultString(Safety_FaultReasonType reason);

#endif /* SWC_SAFETY_MANAGER_H */
