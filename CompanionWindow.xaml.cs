using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using System.Diagnostics;
using System.Runtime.InteropServices;

namespace MiniCompanion
{
    public partial class CompanionWindow : Window
    {
        private Dictionary<string, Dictionary<string, List<BitmapImage>>> animationCache;
        private DispatcherTimer animationTimer;
        private DispatcherTimer windowWatcherTimer;
        private List<BitmapImage> currentFrames;
        private int currentFrameIndex = 0;

        private string currentState = "idle";
        private string currentWindowType = "default";
        private string currentWindowTitle = "default";

        private bool isDragging = false;
        private bool mousePressedOnCompanion = false;
        private double clickStartX = 0;
        private double clickStartY = 0;
        private DateTime clickStartTime;
        private double dragThreshold = 12;
        private double lastClickReactionTime = 0;
        private double clickReactionCooldown = 0.75;

        private double companionX = 200;
        private double companionY = 200;
        private double dragOffsetX = 0;
        private double dragOffsetY = 0;

        private int clicksCount = 0;
        private string currentActiveWindow = "";

        private const int WindowWidth = 120;
        private const int WindowHeight = 120;

        private Dictionary<string, int> FpsPerState = new()
        {
            { "idle", 10 },
            { "watching", 10 },
            { "click", 12 },
            { "window", 10 },
            { "thinking", 10 },
            { "surprised", 12 },
            { "happy", 10 },
            { "yawn", 8 },
            { "dragging", 8 }
        };

        private Dictionary<string, double> DurationPerState = new()
        {
            { "idle", 2.5 },
            { "watching", 2.0 },
            { "click", 0.8 },
            { "window", 1.5 },
            { "thinking", 2.0 },
            { "surprised", 1.0 },
            { "happy", 1.8 },
            { "yawn", 2.0 },
            { "dragging", 0.1 }
        };

        private Dictionary<string, string> FallbackEmojis = new()
        {
            { "idle", "🙂" },
            { "watching", "👀" },
            { "click", "😄" },
            { "window", "🪟" },
            { "thinking", "🤔" },
            { "surprised", "😮" },
            { "happy", "😊" },
            { "yawn", "😴" },
            { "dragging", "✋" }
        };

        private Dictionary<string, List<string>> WindowKeywords = new()
        {
            { "browser", new() { "chrome", "firefox", "edge", "opera", "brave", "browser" } },
            { "editor", new() { "code", "visual studio", "sublime", "notepad", "pycharm", "vscode", "editor" } },
            { "chat", new() { "discord", "telegram", "slack", "teams", "messenger", "signal", "chat" } },
            { "default", new() }
        };

        private List<string> States = new() { "idle", "watching", "click", "window", "thinking", "surprised", "happy", "yawn", "dragging" };

        private string emotionsRoot;

        public CompanionWindow()
        {
            InitializeComponent();

            this.Width = WindowWidth;
            this.Height = WindowHeight;
            this.Left = 200;
            this.Top = 200;
            this.Title = "Mini Companion";
            this.WindowStyle = WindowStyle.None;
            this.AllowsTransparency = true;
            this.Background = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Colors.Transparent);
            this.Topmost = true;
            this.ShowInTaskbar = false;

            MainLabel.FontSize = 48;
            MainLabel.Content = "🙂";

            animationCache = new();
            currentFrames = new();

            emotionsRoot = SelectFolder();
            if (string.IsNullOrEmpty(emotionsRoot))
            {
                MessageBox.Show("Папка з анімаціями не вибрана. Вихід.");
                this.Close();
                return;
            }

            LoadAnimations();
            PrintInfo();

            animationTimer = new();
            animationTimer.Interval = TimeSpan.FromMilliseconds(100);
            animationTimer.Tick += AnimationTimer_Tick;

            windowWatcherTimer = new();
            windowWatcherTimer.Interval = TimeSpan.FromMilliseconds(250);
            windowWatcherTimer.Tick += WindowWatcherTimer_Tick;
            windowWatcherTimer.Start();

            SetState("idle", 2.5, "default");

            this.MouseDown += CompanionWindow_MouseDown;
            this.MouseMove += CompanionWindow_MouseMove;
            this.MouseUp += CompanionWindow_MouseUp;
        }

        private string SelectFolder()
        {
            var dialog = new System.Windows.Forms.FolderBrowserDialog
            {
                Description = "Виберіть папку з анімаціями компаньйона"
            };

            if (dialog.ShowDialog() == System.Windows.Forms.DialogResult.OK)
            {
                return dialog.SelectedPath;
            }

            return null;
        }

        private void PrintInfo()
        {
            Console.WriteLine("\n" + new string('=', 80));
            Console.WriteLine("🎮 Mini Companion — C# версія");
            Console.WriteLine(new string('=', 80));
            Console.WriteLine($"📁 Папка з анімаціями: {emotionsRoot}");
            Console.WriteLine("Структура:");
            Console.WriteLine("  emotions/");
            foreach (var state in States)
            {
                Console.WriteLine($"    {state}/");
                Console.WriteLine("      default/");
                Console.WriteLine("      browser/");
                Console.WriteLine("      editor/");
                Console.WriteLine("      chat/");
            }
            Console.WriteLine(new string('=', 80));
            Console.WriteLine("🎯 Керування:");
            Console.WriteLine("  • Утримуй ЛКМ — перетягування");
            Console.WriteLine("  • Відпусти — зупинити");
            Console.WriteLine("  • Клік по компаньйону — одиночна реакція");
            Console.WriteLine("  • Клік поза компаньйоном — ігнорується");
            Console.WriteLine("  • Зміна активного вікна — реакція під тип вікна");
            Console.WriteLine(new string('=', 80) + "\n");
        }

        private void LoadAnimations()
        {
            Console.WriteLine("🖼️  Завантаження анімацій...");

            if (!Directory.Exists(emotionsRoot))
            {
                Console.WriteLine($"❌ Папка не існує: {emotionsRoot}");
                return;
            }

            int totalLoaded = 0;

            foreach (var state in States)
            {
                string stateDir = Path.Combine(emotionsRoot, state);
                if (!Directory.Exists(stateDir))
                {
                    Console.WriteLine($"⚠️  Папка '{state}' відсутня.");
                    continue;
                }

                animationCache[state] = new();

                var variants = Directory.GetDirectories(stateDir);
                if (variants.Length == 0)
                {
                    variants = new[] { stateDir };
                }

                foreach (var variant in variants)
                {
                    string variantName = Path.GetFileName(variant);
                    if (variantName == state)
                        variantName = "default";

                    var frames = new List<BitmapImage>();
                    var pngFiles = Directory.GetFiles(variant, "frame_*.png").OrderBy(f => f);

                    foreach (var file in pngFiles)
                    {
                        try
                        {
                            var bitmap = new BitmapImage();
                            bitmap.BeginInit();
                            bitmap.UriSource = new Uri(file);
                            bitmap.CacheOption = BitmapCacheOption.OnLoad;
                            bitmap.EndInit();
                            bitmap.Freeze();
                            frames.Add(bitmap);
                        }
                        catch (Exception ex)
                        {
                            Console.WriteLine($"❌ Не вдалось завантажити {file}: {ex.Message}");
                        }
                    }

                    if (frames.Count > 0)
                    {
                        animationCache[state][variantName] = frames;
                        Console.WriteLine($"   ✅ {state}/{variantName}: {frames.Count} кадрів");
                        totalLoaded++;
                    }
                }
            }

            Console.WriteLine($"\n📊 Завантажено: {totalLoaded} анімаційних варіантів");
            if (totalLoaded == 0)
            {
                Console.WriteLine("⚠️  Немає анімацій — будуть використовуватися стандартні емодзі.\n");
            }
        }

        private string DetectWindowType(string title)
        {
            string text = title.ToLower();

            foreach (var kvp in WindowKeywords)
            {
                if (kvp.Key == "default")
                    continue;

                if (kvp.Value.Any(keyword => text.Contains(keyword)))
                {
                    return kvp.Key;
                }
            }

            return "default";
        }

        private List<BitmapImage> ChooseFramesForState(string state, string windowTitle)
        {
            string windowType = DetectWindowType(windowTitle);

            if (animationCache.ContainsKey(state))
            {
                var variantMap = animationCache[state];

                if (variantMap.ContainsKey(windowType) && variantMap[windowType].Count > 0)
                {
                    return variantMap[windowType];
                }

                if (variantMap.ContainsKey("default") && variantMap["default"].Count > 0)
                {
                    return variantMap["default"];
                }

                foreach (var frames in variantMap.Values)
                {
                    if (frames.Count > 0)
                    {
                        return frames;
                    }
                }
            }

            return new();
        }

        private void ShowFallbackEmoji()
        {
            MainLabel.Content = FallbackEmojis.ContainsKey(currentState) ? FallbackEmojis[currentState] : "🙂";
        }

        private void ShowCurrentFrame()
        {
            if (currentFrames.Count == 0)
            {
                ShowFallbackEmoji();
                return;
            }

            MainLabel.Content = currentFrames[currentFrameIndex];
        }

        private void AnimationTimer_Tick(object sender, EventArgs e)
        {
            if (isDragging)
            {
                return;
            }

            if (currentFrames.Count == 0)
            {
                ShowFallbackEmoji();
                return;
            }

            ShowCurrentFrame();
            currentFrameIndex = (currentFrameIndex + 1) % currentFrames.Count;
        }

        private void SetState(string state, double? duration = null, string windowTitle = null)
        {
            if (!States.Contains(state))
            {
                return;
            }

            if (isDragging && state != "dragging")
            {
                return;
            }

            animationTimer.Stop();

            currentState = state;
            if (!string.IsNullOrEmpty(windowTitle))
            {
                currentWindowTitle = windowTitle;
            }
            else
            {
                currentWindowTitle = currentWindowTitle ?? "default";
            }

            currentWindowType = DetectWindowType(currentWindowTitle);
            currentFrames = ChooseFramesForState(state, currentWindowTitle);

            if (currentFrames.Count > 0)
            {
                currentFrameIndex = 0;
                ShowCurrentFrame();

                int fps = FpsPerState.ContainsKey(state) ? FpsPerState[state] : 10;
                int delay = 1000 / fps;
                animationTimer.Interval = TimeSpan.FromMilliseconds(delay);
                animationTimer.Start();
            }
            else
            {
                ShowFallbackEmoji();
            }

            if (!isDragging && state != "idle")
            {
                double durationValue = duration ?? (DurationPerState.ContainsKey(state) ? DurationPerState[state] : 1.5);
                this.Dispatcher.BeginInvoke(new Action(() =>
                {
                    var timer = new DispatcherTimer();
                    timer.Interval = TimeSpan.FromSeconds(durationValue);
                    timer.Tick += (s, e) =>
                    {
                        if (currentState == state)
                        {
                            SetState("idle", DurationPerState["idle"], currentWindowTitle);
                        }
                        timer.Stop();
                    };
                    timer.Start();
                }));
            }
        }

        private void CompanionWindow_MouseDown(object sender, System.Windows.Input.MouseEventArgs e)
        {
            var pos = e.GetPosition(this);

            if (pos.X >= 0 && pos.X <= this.Width && pos.Y >= 0 && pos.Y <= this.Height)
            {
                if (e.LeftButton == System.Windows.Input.MouseButtonState.Pressed)
                {
                    mousePressedOnCompanion = true;
                    clickStartX = pos.X;
                    clickStartY = pos.Y;
                    clickStartTime = DateTime.Now;
                    return;
                }
            }
        }

        private void CompanionWindow_MouseMove(object sender, System.Windows.Input.MouseEventArgs e)
        {
            var screenPos = e.GetPosition(new Window());

            if (mousePressedOnCompanion && !isDragging)
            {
                double movementX = Math.Abs(screenPos.X - clickStartX);
                double movementY = Math.Abs(screenPos.Y - clickStartY);

                if (movementX > dragThreshold || movementY > dragThreshold)
                {
                    isDragging = true;
                    dragOffsetX = screenPos.X - companionX;
                    dragOffsetY = screenPos.Y - companionY;
                    SetState("dragging", 0.1, currentWindowTitle);
                    Console.WriteLine("✋ Почали перетягування");
                }
            }

            if (isDragging)
            {
                double newX = screenPos.X - dragOffsetX;
                double newY = screenPos.Y - dragOffsetY;

                var screenSize = System.Windows.Forms.Screen.PrimaryScreen.WorkingArea;

                newX = Math.Max(0, Math.Min(newX, screenSize.Width - this.Width));
                newY = Math.Max(0, Math.Min(newY, screenSize.Height - this.Height));

                companionX = newX;
                companionY = newY;
                this.Left = newX;
                this.Top = newY;

                if (currentState != "dragging")
                {
                    SetState("dragging", 0.1, currentWindowTitle);
                }
            }
        }

        private void CompanionWindow_MouseUp(object sender, System.Windows.Input.MouseEventArgs e)
        {
            if (mousePressedOnCompanion)
            {
                mousePressedOnCompanion = false;

                double pressDuration = (DateTime.Now - clickStartTime).TotalSeconds;
                double movementX = Math.Abs(e.GetPosition(this).X - clickStartX);
                double movementY = Math.Abs(e.GetPosition(this).Y - clickStartY);

                if (pressDuration < 0.5 && movementX < dragThreshold && movementY < dragThreshold)
                {
                    double now = DateTime.Now.Ticks / 10000000.0;
                    if (now - lastClickReactionTime >= clickReactionCooldown)
                    {
                        lastClickReactionTime = now;
                        clicksCount++;
                        SetState("click", 0.7, currentWindowTitle);
                        Console.WriteLine($"👆 Одинарний клік по компаньйону! Всього: {clicksCount}");
                        return;
                    }
                }

                if (isDragging)
                {
                    isDragging = false;
                    SetState("idle", 2.5, currentWindowTitle);
                    Console.WriteLine("🛑 Відпустили компаньйона");
                }
            }
        }

        private void WindowWatcherTimer_Tick(object sender, EventArgs e)
        {
            try
            {
                Process[] processes = Process.GetProcesses();
                Process activeProcess = processes.FirstOrDefault(p => p.MainWindowHandle != IntPtr.Zero);

                if (activeProcess != null)
                {
                    string title = activeProcess.MainWindowTitle;

                    if (title != currentActiveWindow)
                    {
                        currentActiveWindow = title;
                        currentWindowTitle = title;

                        string detected = DetectWindowType(title);
                        Console.WriteLine($"🪟 Активне вікно: {title.Substring(0, Math.Min(60, title.Length))} | тип: {detected}");

                        if (isDragging)
                        {
                            return;
                        }

                        if (title.ToLower().Contains("chrome") || title.ToLower().Contains("firefox") || 
                            title.ToLower().Contains("edge") || title.ToLower().Contains("opera") || 
                            title.ToLower().Contains("brave"))
                        {
                            SetState("thinking", 2.0, title);
                        }
                        else if (title.ToLower().Contains("code") || title.ToLower().Contains("visual studio") || 
                                 title.ToLower().Contains("sublime") || title.ToLower().Contains("notepad") || 
                                 title.ToLower().Contains("pycharm") || title.ToLower().Contains("vscode"))
                        {
                            SetState("window", 1.5, title);
                        }
                        else if (title.ToLower().Contains("discord") || title.ToLower().Contains("telegram") || 
                                 title.ToLower().Contains("slack") || title.ToLower().Contains("teams") || 
                                 title.ToLower().Contains("messenger") || title.ToLower().Contains("signal"))
                        {
                            SetState("happy", 1.8, title);
                        }
                        else
                        {
                            SetState("window", 1.5, title);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                // Мовчазно ігноруємо помилки
            }
        }
    }
}
