%% matlab_import_sysid.m
% Automotive Domain Gateway & Real-Time Motor Controller (STM32MP157D-DK1)
% Week 5 & Week 6: System Identification & Discrete PID Tuning
%
% This script imports the experimental step response CSV data captured by
% gateway_a7/step_logger.py, estimates the continuous FOPDT transfer function
% G(s) = K / (tau*s + 1) * exp(-theta*s), discretizes to Ts = 0.01s (10ms),
% and computes optimal digital PID parameters for SWC_MotorControl.

clear; clc; close all;

%% 1. Configuration & Data Import
Ts = 0.01; % 10ms real-time sampling period (AUTOSAR FR-M3 & NFR-1)

data_dir = fullfile(fileparts(mfilename('fullpath')), 'data');
file_40 = fullfile(data_dir, 'step_response_40.csv');
file_60 = fullfile(data_dir, 'step_response_60.csv');
file_80 = fullfile(data_dir, 'step_response_80.csv');

fprintf('=================================================================\n');
fprintf('  STM32MP157D-DK1 MOTOR SYSTEM IDENTIFICATION & PID DESIGN       \n');
fprintf('  Sampling Time Ts = %.3f s (100 Hz AUTOSAR Loop)               \n');
fprintf('=================================================================\n\n');

% Load data if available
if exist(file_60, 'file')
    opts = detectImportOptions(file_60);
    tbl_60 = readtable(file_60, opts);
    fprintf('Loaded %s: %d samples\n', file_60, height(tbl_60));
elseif exist('step_response_60.csv', 'file')
    opts = detectImportOptions('step_response_60.csv');
    tbl_60 = readtable('step_response_60.csv', opts);
    fprintf('Loaded step_response_60.csv: %d samples\n', height(tbl_60));
else
    fprintf('[WARN] File step_response_60.csv not found. Using representative experimental model.\n');
    % Fallback synthetic model matching JGA25-370-46.8K hardware:
    % K = 0.182 RPM/%, tau = 0.12s, theta = 0.02s
    t_sim = (0:Ts:4.0)';
    u_sim = [zeros(50, 1); 60*ones(351, 1)];
    sys_true = tf(0.182, [0.12 1], 'InputDelay', 0.02);
    y_sim = lsim(sys_true, u_sim, t_sim) + 0.1*randn(size(t_sim));
    tbl_60 = table(t_sim*1000, u_sim, y_sim, 'VariableNames', {'time_ms', 'duty_pct', 'speed_rpm'});
end

% Adapt column names for compatibility with step5.py CSV format
if ismember('time_ms', tbl_60.Properties.VariableNames)
    t = tbl_60.time_ms / 1000.0; % Convert ms to seconds
elseif ismember('time_s', tbl_60.Properties.VariableNames)
    t = tbl_60.time_s;
else
    t = (0:height(tbl_60)-1)' * Ts;
end

if ismember('speed_rpm', tbl_60.Properties.VariableNames)
    y = tbl_60.speed_rpm;
elseif ismember('rpm', tbl_60.Properties.VariableNames)
    y = tbl_60.rpm;
else
    y = tbl_60{:, 3};
end

if ismember('duty_pct', tbl_60.Properties.VariableNames)
    u = tbl_60.duty_pct;
else
    u = tbl_60{:, 2};
end

%% 2. Plot Raw Step Response
figure('Name', 'Experimental Step Response (60% Duty)', 'Position', [100 100 850 550]);
subplot(2,1,1);
plot(t, u, 'LineWidth', 1.8, 'Color', [0.85 0.33 0.10]);
grid on; grid minor;
ylabel('PWM Duty Cycle [%]', 'FontWeight', 'bold');
title('Motor Excitation Input u(t)', 'FontSize', 12);
ylim([-5 100]);

subplot(2,1,2);
plot(t, y, 'LineWidth', 1.8, 'Color', [0 0.45 0.74]);
grid on; grid minor;
xlabel('Time [s]', 'FontWeight', 'bold');
ylabel('Speed \omega [RPM]', 'FontWeight', 'bold');
title('Measured Output Speed y(t) from Hall Encoder', 'FontSize', 12);

%% 3. System Identification (System Identification Toolbox)
fprintf('\n--- 2. Estimating FOPDT Model G(s) = K / (tau*s + 1) * exp(-theta*s) ---\n');
% Create iddata object
data = iddata(y, u, Ts, 'Name', 'JGA25-370 Step Response');
data.InputName = 'Duty';
data.InputUnit = '%';
data.OutputName = 'Speed';
data.OutputUnit = 'RPM';

% Estimate 1st order continuous transfer function with I/O delay
try
    sys_est = tfest(data, 1, 0, 'IODelay', NaN);
    fprintf('Estimated Transfer Function:\n');
    sys_est
    
    % Model validation
    figure('Name', 'Model Validation vs Measured Data', 'Position', [150 150 800 500]);
    compare(data, sys_est);
    grid on; grid minor;
    title('Measured Data vs Estimated Model Fit');
catch ME
    fprintf('[NOTE] tfest requires System Identification Toolbox (%s).\n', ME.message);
    % Parametric analytical fit from steady state and 63.2% rise time
    u_base = u(1);
    u_step = max(u);
    delta_u = u_step - u_base;
    
    y_base = mean(y(1:min(50, length(y))));
    y_ss = mean(y(end-min(50, length(y)):end));
    delta_y = y_ss - y_base;
    
    K_static = delta_y / delta_u;
    y_632 = y_base + 0.632 * delta_y;
    
    idx_step = find(diff(u) > 10, 1, 'first');
    t_step_start = t(idx_step);
    
    idx_632 = find(y >= y_632, 1, 'first');
    tau_est = t(idx_632) - t_step_start;
    if tau_est <= 0, tau_est = 0.12; end
    
    theta_est = 0.02; % 2 sampling periods
    sys_est = tf(K_static, [tau_est 1], 'InputDelay', theta_est);
    fprintf('Analytical FOPDT Model: K = %.3f RPM/%%, tau = %.3f s, theta = %.3f s\n', ...
            K_static, tau_est, theta_est);
    sys_est
end

%% 4. Discretization & Digital PID Controller Design
fprintf('\n--- 3. Discretizing Continuous Plant to Ts = 0.01s (ZOH) ---\n');
sys_d = c2d(sys_est, Ts, 'zoh');
sys_d

fprintf('\n--- 4. Tuning Discrete PID Controller (Control System Toolbox) ---\n');
try
    % Design PI/PID for good phase margin (PM >= 60 deg, Settling Time < 300ms)
    opts_pid = pidtuneOptions('PhaseMargin', 65, 'DesignFocus', 'reference-tracking');
    [C_pi, info] = pidtune(sys_est, 'PI', 15, opts_pid); % Bandwidth ~ 15 rad/s
    fprintf('Optimal Continuous PI Controller:\n');
    C_pi
    
    % Discretize controller using Backward Euler or Trapezoidal (Tustin)
    C_pid_d = c2d(C_pi, Ts, 'tustin');
    fprintf('Optimal Discrete PI Controller (Ts = 0.01s):\n');
    C_pid_d
    
    Kp = C_pi.Kp;
    Ki = C_pi.Ki;
    Kd = 0.0; % PI is standard for velocity loops
    
    fprintf('\n=================================================================\n');
    fprintf('  RECOMMENDED AUTOSAR SWC_MotorControl PARAMETERS (WEEK 7):      \n');
    fprintf('  - K_KP = %.4ff\n', Kp);
    fprintf('  - K_KI = %.4ff\n', Ki);
    fprintf('  - K_KD = %.4ff\n', Kd);
    fprintf('  - K_DT = 0.01f  (Ts = 10ms)\n');
    fprintf('=================================================================\n');
catch ME
    fprintf('[NOTE] pidtune note: %s\n', ME.message);
end

%% 5. Closed-Loop Step Simulation
try
    T_cl = feedback(C_pi * sys_est, 1);
    figure('Name', 'Closed-Loop PID Tracking Simulation', 'Position', [200 200 800 450]);
    step(60 * T_cl, 2.0);
    grid on; grid minor;
    title('Closed-Loop Speed Setpoint Step Tracking (60 RPM)', 'FontWeight', 'bold');
    ylabel('Speed [RPM]');
    xlabel('Time [s]');
catch
end
