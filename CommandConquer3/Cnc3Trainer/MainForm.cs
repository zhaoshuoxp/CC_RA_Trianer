using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Windows.Forms;

namespace Cnc3Trainer
{
    internal sealed class MainForm : Form
    {
        readonly Color Back = Color.FromArgb(15, 19, 24);
        readonly Color Card = Color.FromArgb(25, 31, 38);
        readonly Color Card2 = Color.FromArgb(33, 40, 48);
        readonly Color TextMain = Color.FromArgb(232, 237, 241);
        readonly Color TextMuted = Color.FromArgb(145, 158, 171);
        readonly Color Accent = Color.FromArgb(54, 190, 120);
        readonly Color Danger = Color.FromArgb(224, 83, 83);
        readonly TrainerEngine engine = new TrainerEngine();
        readonly Timer timer = new Timer();
        readonly Dictionary<int, bool> hotkeyState = new Dictionary<int, bool>();

        Label statusDot, statusText, gameText, moneyCurrent, hintText;
        Button connectButton, setMoneyButton, addMoneyButton;
        NumericUpDown moneyInput;
        CheckBox keepMoney, power, god, scenario, shield, quick, global;
        bool updating;

        internal MainForm()
        {
            Text = "命令与征服 3 修改器";
            ClientSize = new Size(560, 630);
            MinimumSize = new Size(576, 669);
            MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Back;
            ForeColor = TextMain;
            Font = new Font("Microsoft YaHei UI", 9F);
            BuildUi();
            timer.Interval = 100;
            timer.Tick += TimerTick;
            timer.Start();
            FormClosing += delegate { try { engine.Dispose(); } catch { } };
        }

        void BuildUi()
        {
            Label title = MakeLabel("COMMAND & CONQUER 3", 22F, FontStyle.Bold, TextMain);
            title.Location = new Point(28, 22); title.AutoSize = true;
            Controls.Add(title);
            Label subtitle = MakeLabel("泰伯利亚战争 / 凯恩之怒 · 单人修改器", 10F, FontStyle.Regular, TextMuted);
            subtitle.Location = new Point(31, 58); subtitle.AutoSize = true; Controls.Add(subtitle);

            Panel status = MakeCard(new Rectangle(24, 92, 512, 76));
            statusDot = MakeLabel("●", 13F, FontStyle.Regular, Danger); statusDot.Location = new Point(18, 15); statusDot.AutoSize = true;
            statusText = MakeLabel("未连接", 11F, FontStyle.Bold, TextMain); statusText.Location = new Point(46, 13); statusText.AutoSize = true;
            gameText = MakeLabel("请先进入单人战役或遭遇战地图", 8.5F, FontStyle.Regular, TextMuted); gameText.Location = new Point(47, 41); gameText.AutoSize = true;
            connectButton = MakeButton("连接游戏  [Num *]", new Rectangle(326, 17, 165, 42), Accent);
            connectButton.Click += delegate { ToggleConnection(); };
            status.Controls.Add(statusDot); status.Controls.Add(statusText); status.Controls.Add(gameText); status.Controls.Add(connectButton); Controls.Add(status);

            Label moneyTitle = SectionTitle("资源", 194); Controls.Add(moneyTitle);
            Panel moneyCard = MakeCard(new Rectangle(24, 224, 512, 120)); Controls.Add(moneyCard);
            Label currentCaption = MakeLabel("当前资金", 8.5F, FontStyle.Regular, TextMuted); currentCaption.Location = new Point(18, 14); currentCaption.AutoSize = true;
            moneyCurrent = MakeLabel("—", 20F, FontStyle.Bold, TextMain); moneyCurrent.Location = new Point(16, 34); moneyCurrent.AutoSize = true;
            moneyInput = new NumericUpDown(); moneyInput.Location = new Point(160, 22); moneyInput.Size = new Size(150, 34); moneyInput.Maximum = 2000000000; moneyInput.Value = 50000; moneyInput.Increment = 10000;
            moneyInput.BackColor = Card2; moneyInput.ForeColor = TextMain; moneyInput.BorderStyle = BorderStyle.FixedSingle; moneyInput.Font = new Font(Font.FontFamily, 12F, FontStyle.Bold);
            setMoneyButton = MakeButton("设置", new Rectangle(321, 20, 78, 38), Color.FromArgb(65, 106, 158));
            setMoneyButton.Click += delegate { RunAction(delegate { engine.SetMoney((int)moneyInput.Value); }); };
            addMoneyButton = MakeButton("+10 万", new Rectangle(407, 20, 86, 38), Color.FromArgb(65, 106, 158));
            addMoneyButton.Click += delegate { RunAction(delegate { engine.AddMoney(100000); }); };
            keepMoney = MakeToggle("保持最低金额", "Num 1", new Point(160, 76));
            keepMoney.CheckedChanged += delegate { if (!updating) { engine.MinimumTarget = (int)moneyInput.Value; engine.MinimumMoney = keepMoney.Checked; PaintToggle(keepMoney); } };
            moneyInput.ValueChanged += delegate { engine.MinimumTarget = (int)moneyInput.Value; };
            moneyCard.Controls.Add(currentCaption); moneyCard.Controls.Add(moneyCurrent); moneyCard.Controls.Add(moneyInput); moneyCard.Controls.Add(setMoneyButton); moneyCard.Controls.Add(addMoneyButton); moneyCard.Controls.Add(keepMoney);

            Label featureTitle = SectionTitle("战场功能", 370); Controls.Add(featureTitle);
            Panel featureCard = MakeCard(new Rectangle(24, 400, 512, 150)); Controls.Add(featureCard);
            power = MakeToggle("无限电力", "Num 2", new Point(18, 16));
            god = MakeToggle("我方无敌", "Num 3", new Point(260, 16));
            scenario = MakeToggle("保护剧情初始单位", "Num 4", new Point(18, 60));
            shield = MakeToggle("护盾不减", "Num 5", new Point(260, 60));
            quick = MakeToggle("快速生产", "Num 6", new Point(18, 104));
            global = MakeToggle("全球征服资金", "Num 7", new Point(260, 104));
            power.CheckedChanged += delegate { if (!updating) { engine.UnlimitedPower = power.Checked; PaintToggle(power); } };
            god.CheckedChanged += delegate { if (!updating) { RunFeature(god, delegate(bool v) { engine.SetGod(v); }); } };
            scenario.CheckedChanged += delegate { if (!updating) { RunFeature(scenario, delegate(bool v) { engine.SetScenarioProtection(v); }); } };
            shield.CheckedChanged += delegate { if (!updating) { RunFeature(shield, delegate(bool v) { engine.SetShield(v); }); } };
            quick.CheckedChanged += delegate { if (!updating) { RunFeature(quick, delegate(bool v) { engine.SetQuick(v); }); } };
            global.CheckedChanged += delegate { if (!updating) { RunFeature(global, delegate(bool v) { engine.SetGlobal(v); }); } };
            featureCard.Controls.Add(power); featureCard.Controls.Add(god); featureCard.Controls.Add(scenario); featureCard.Controls.Add(shield); featureCard.Controls.Add(quick); featureCard.Controls.Add(global);

            hintText = MakeLabel("仅限单人模式 · 读档或进入新地图会自动关闭功能 · 正常退出将恢复指令", 8.5F, FontStyle.Regular, TextMuted);
            hintText.Location = new Point(29, 576); hintText.AutoSize = true; Controls.Add(hintText);
            SetControlsEnabled(false);
        }

        Label SectionTitle(string text, int y)
        {
            Label label = MakeLabel(text, 10F, FontStyle.Bold, TextMuted); label.Location = new Point(28, y); label.AutoSize = true; return label;
        }

        Panel MakeCard(Rectangle bounds) { Panel panel = new Panel(); panel.Bounds = bounds; panel.BackColor = Card; return panel; }
        Label MakeLabel(string text, float size, FontStyle style, Color color) { Label label = new Label(); label.Text = text; label.ForeColor = color; label.Font = new Font("Microsoft YaHei UI", size, style); label.BackColor = Color.Transparent; return label; }

        Button MakeButton(string text, Rectangle bounds, Color color)
        {
            Button button = new Button(); button.Text = text; button.Bounds = bounds; button.BackColor = color; button.ForeColor = Color.White; button.FlatStyle = FlatStyle.Flat; button.FlatAppearance.BorderSize = 0; button.Cursor = Cursors.Hand; button.Font = new Font(Font.FontFamily, 9F, FontStyle.Bold); return button;
        }

        CheckBox MakeToggle(string text, string key, Point point)
        {
            CheckBox box = new CheckBox(); box.Appearance = Appearance.Button; box.FlatStyle = FlatStyle.Flat; box.FlatAppearance.BorderSize = 1; box.FlatAppearance.BorderColor = Color.FromArgb(55, 65, 75); box.BackColor = Card2; box.ForeColor = TextMain;
            box.Text = text + "     " + key; box.TextAlign = ContentAlignment.MiddleCenter; box.Location = point; box.Size = new Size(224, 34); box.Cursor = Cursors.Hand; return box;
        }

        void PaintToggle(CheckBox box)
        {
            box.BackColor = box.Checked ? Color.FromArgb(35, 116, 78) : Card2;
            box.FlatAppearance.BorderColor = box.Checked ? Accent : Color.FromArgb(55, 65, 75);
        }

        void ToggleConnection()
        {
            if (engine.IsConnected) { DisconnectUi("已断开并恢复原始指令"); return; }
            try
            {
                engine.Connect(); SetControlsEnabled(true); global.Enabled = engine.SupportsGlobalResource;
                statusDot.ForeColor = Accent; statusText.Text = "已连接 · 等待地图数据";
                gameText.Text = engine.GameName + "  " + engine.Version + "  · PID " + engine.ProcessId;
                connectButton.Text = "断开并恢复  [Num *]"; connectButton.BackColor = Color.FromArgb(171, 76, 76);
            }
            catch (Exception ex) { MessageBox.Show(this, ex.Message, "无法连接", MessageBoxButtons.OK, MessageBoxIcon.Warning); DisconnectUi("未连接"); }
        }

        void DisconnectUi(string message)
        {
            try { engine.Disconnect(); } catch { }
            ResetChecks(); SetControlsEnabled(false); moneyCurrent.Text = "—"; statusDot.ForeColor = Danger; statusText.Text = message;
            gameText.Text = "请先进入单人战役或遭遇战地图"; connectButton.Text = "连接游戏  [Num *]"; connectButton.BackColor = Accent;
        }

        void SetControlsEnabled(bool enabled)
        {
            moneyInput.Enabled = enabled; setMoneyButton.Enabled = enabled; addMoneyButton.Enabled = enabled; keepMoney.Enabled = enabled;
            power.Enabled = enabled; god.Enabled = enabled; scenario.Enabled = enabled; shield.Enabled = enabled; quick.Enabled = enabled; global.Enabled = enabled && engine.SupportsGlobalResource;
        }

        void ResetChecks()
        {
            updating = true;
            keepMoney.Checked = power.Checked = god.Checked = scenario.Checked = shield.Checked = quick.Checked = global.Checked = false;
            foreach (CheckBox box in new CheckBox[] { keepMoney, power, god, scenario, shield, quick, global }) PaintToggle(box);
            updating = false;
        }

        void RunFeature(CheckBox box, Action<bool> action)
        {
            try { action(box.Checked); PaintToggle(box); }
            catch (Exception ex) { updating = true; box.Checked = !box.Checked; updating = false; PaintToggle(box); MessageBox.Show(this, ex.Message, "操作失败", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
        }

        void RunAction(Action action)
        {
            try { if (!engine.IsConnected) throw new InvalidOperationException("请先连接游戏。"); action(); }
            catch (Exception ex) { MessageBox.Show(this, ex.Message, "操作失败", MessageBoxButtons.OK, MessageBoxIcon.Warning); }
        }

        void TimerTick(object sender, EventArgs e)
        {
            try
            {
                if (!engine.IsConnected)
                {
                    bool gameForeground = IsUnattachedGameForeground();
                    if (gameForeground && Pressed(0x6A)) ToggleConnection();
                    else if (!gameForeground) hotkeyState.Clear();
                    return;
                }
                if (engine.IsConnected)
                {
                    TickResult result = engine.Tick();
                    if (!engine.IsConnected) { DisconnectUi("游戏已退出"); return; }
                    if (result.SessionChanged) { ResetChecks(); statusText.Text = "检测到新地图，功能已关闭"; }
                    if (result.PlayerReady) { moneyCurrent.Text = result.Money.ToString("N0"); if (!result.SessionChanged) statusText.Text = "已连接 · 单人地图就绪"; }
                    else { moneyCurrent.Text = "—"; statusText.Text = "已连接 · 请进入或恢复地图"; }
                    PollHotkeys();
                }
            }
            catch (Exception ex) { DisconnectUi("连接已中断"); gameText.Text = ex.Message; }
        }

        bool IsUnattachedGameForeground()
        {
            IntPtr window = NativeMethods.GetForegroundWindow(); uint pid;
            NativeMethods.GetWindowThreadProcessId(window, out pid);
            if (pid == 0) return false;
            try
            {
                string name = Process.GetProcessById((int)pid).ProcessName.ToLowerInvariant();
                return name.Contains("cnc3game") || name.Contains("cnc3ep1");
            }
            catch { return false; }
        }

        void PollHotkeys()
        {
            if (!engine.IsGameForeground()) { hotkeyState.Clear(); return; }
            if (Pressed(0x6A)) { ToggleConnection(); return; }
            if (Pressed(0x61)) keepMoney.Checked = !keepMoney.Checked;
            if (Pressed(0x62)) power.Checked = !power.Checked;
            if (Pressed(0x63)) god.Checked = !god.Checked;
            if (Pressed(0x64)) scenario.Checked = !scenario.Checked;
            if (Pressed(0x65)) shield.Checked = !shield.Checked;
            if (Pressed(0x66)) quick.Checked = !quick.Checked;
            if (global.Enabled && Pressed(0x67)) global.Checked = !global.Checked;
        }

        bool Pressed(int key)
        {
            bool down = (NativeMethods.GetAsyncKeyState(key) & 0x8000) != 0;
            bool before; hotkeyState.TryGetValue(key, out before); hotkeyState[key] = down; return down && !before;
        }
    }
}
