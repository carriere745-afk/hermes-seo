<?php
/**
 * Hermes SEO — WordPress Integration Plugin
 *
 * Shortcodes pour integrer les outils SEO gratuits dans WordPress.
 * Blog auto-alimente par Hermes P1.
 *
 * Usage:
 *   [hermes_tool name="serp_preview"]
 *   [hermes_tool name="word_counter"]
 *   [hermes_score url="https://example.com"]
 *
 * Version: 3.0
 * Author: FC Solutions
 */

if (!defined('ABSPATH')) {
    exit; // Exit if accessed directly
}

// ============================================================
// 1. SERP Preview Tool
// ============================================================
function hermes_serp_preview_shortcode($atts) {
    $atts = shortcode_atts(['title' => '', 'desc' => '', 'url' => ''], $atts);
    ob_start(); ?>
    <div class="hermes-tool" style="max-width:700px;margin:20px auto;padding:20px;background:#f8fafc;border-radius:12px;font-family:Arial,sans-serif">
        <h3 style="margin-top:0">Apercu SERP Google</h3>
        <form method="post" class="hermes-form">
            <label>Meta Title (50-60 caracteres recommandes)</label>
            <input type="text" name="hermes_title" value="<?php echo esc_attr($_POST['hermes_title'] ?? $atts['title']); ?>"
                   style="width:100%;padding:8px;margin:5px 0 15px;border:1px solid #ddd;border-radius:4px" maxlength="100">

            <label>Meta Description (120-155 caracteres recommandes)</label>
            <textarea name="hermes_desc" rows="3" style="width:100%;padding:8px;margin:5px 0 15px;border:1px solid #ddd;border-radius:4px" maxlength="200"><?php echo esc_textarea($_POST['hermes_desc'] ?? $atts['desc']); ?></textarea>

            <label>URL</label>
            <input type="text" name="hermes_url" value="<?php echo esc_attr($_POST['hermes_url'] ?? $atts['url']); ?>"
                   style="width:100%;padding:8px;margin:5px 0 15px;border:1px solid #ddd;border-radius:4px">

            <button type="submit" style="background:#1E88E5;color:#fff;border:none;padding:10px 24px;border-radius:6px;cursor:pointer;font-weight:600">Generer l'apercu</button>
        </form>

        <?php if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['hermes_title'])):
            $title = sanitize_text_field($_POST['hermes_title']);
            $desc = sanitize_textarea_field($_POST['hermes_desc']);
            $url = esc_url($_POST['hermes_url']);
            $title_len = strlen($title);
            $desc_len = strlen($desc);
            $title_status = $title_len >= 30 && $title_len <= 65 ? 'Optimal' : ($title_len < 30 ? 'Trop court' : 'Trop long');
            $desc_status = $desc_len >= 70 && $desc_len <= 160 ? 'Optimal' : ($desc_len < 70 ? 'Trop court' : 'Trop long');
        ?>
            <div style="margin-top:20px;padding:15px;background:#fff;border:1px solid #e2e8f0;border-radius:8px">
                <h4>Apercu dans Google:</h4>
                <div style="color:#1a0dab;font-size:18px;line-height:1.3;margin-bottom:3px"><?php echo esc_html($title); ?></div>
                <div style="color:#006621;font-size:14px;line-height:1.4"><?php echo parse_url($url, PHP_URL_HOST) ?: 'example.com'; ?></div>
                <div style="color:#545454;font-size:13px;line-height:1.4"><?php echo esc_html($desc); ?></div>
            </div>
            <p style="font-size:13px;color:#666;margin-top:10px">
                Title: <?php echo $title_len; ?> caracteres (<?php echo $title_status; ?>) |
                Description: <?php echo $desc_len; ?> caracteres (<?php echo $desc_status; ?>)
            </p>
        <?php endif; ?>

        <p style="font-size:12px;color:#999;margin-top:20px;border-top:1px solid #eee;padding-top:10px">
            Outil gratuit par <strong>Hermes SEO</strong>. Pour une analyse complete, <a href="/app/">essayez Hermes SEO Pro</a>.
        </p>
    </div>
    <?php
    return ob_get_clean();
}
add_shortcode('hermes_serp', 'hermes_serp_preview_shortcode');


// ============================================================
// 2. Word Counter Tool
// ============================================================
function hermes_word_counter_shortcode() {
    ob_start(); ?>
    <div class="hermes-tool" style="max-width:700px;margin:20px auto;padding:20px;background:#f8fafc;border-radius:12px;font-family:Arial,sans-serif">
        <h3 style="margin-top:0">Compteur de Mots & Analyse SEO</h3>
        <form method="post">
            <textarea name="hermes_text" rows="8" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:4px"
                      placeholder="Collez votre texte ici..."><?php echo esc_textarea($_POST['hermes_text'] ?? ''); ?></textarea>
            <button type="submit" style="background:#1E88E5;color:#fff;border:none;padding:10px 24px;border-radius:6px;cursor:pointer;font-weight:600;margin-top:10px">Analyser</button>
        </form>

        <?php if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['hermes_text'])):
            $text = sanitize_textarea_field($_POST['hermes_text']);
            $words = str_word_count($text, 0);
            $chars = strlen($text);
            $chars_no_spaces = strlen(str_replace(' ', '', $text));
            $sentences = max(1, preg_match_all('/[.!?]+/', $text));
            $reading_time = ceil($words / 238);

            // Keyword density
            $word_list = str_word_count(strtolower($text), 1);
            $word_freq = array_count_values(array_filter($word_list, function($w) { return strlen($w) >= 4; }));
            arsort($word_freq);
            $top_words = array_slice($word_freq, 0, 10, true);
        ?>
            <div style="margin-top:20px;display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
                <div style="background:#fff;padding:10px;border-radius:8px;text-align:center">
                    <strong style="font-size:1.5rem"><?php echo $words; ?></strong><br><small>Mots</small>
                </div>
                <div style="background:#fff;padding:10px;border-radius:8px;text-align:center">
                    <strong style="font-size:1.5rem"><?php echo $chars; ?></strong><br><small>Caracteres</small>
                </div>
                <div style="background:#fff;padding:10px;border-radius:8px;text-align:center">
                    <strong style="font-size:1.5rem"><?php echo $reading_time; ?> min</strong><br><small>Temps de lecture</small>
                </div>
            </div>

            <h4 style="margin-top:15px">Mots-cles principaux:</h4>
            <div style="display:flex;flex-wrap:wrap;gap:8px">
                <?php foreach ($top_words as $word => $count):
                    $density = round($count / max($words, 1) * 100, 1); ?>
                    <span style="background:#e3f2fd;color:#1565c0;padding:4px 10px;border-radius:20px;font-size:13px">
                        <?php echo esc_html($word); ?> (<?php echo $density; ?>%)
                    </span>
                <?php endforeach; ?>
            </div>

            <?php if ($words < 300): ?>
                <p style="color:#e65100">Ce contenu est court (<300 mots). Google considere cela comme du thin content.</p>
            <?php endif; ?>
        <?php endif; ?>

        <p style="font-size:12px;color:#999;margin-top:20px;border-top:1px solid #eee;padding-top:10px">
            Limite: 5000 mots en version gratuite. <a href="/app/">Hermes SEO Pro</a> analyse jusqu'a 50000 mots avec 7 dimensions SEO/AEO/GEO.
        </p>
    </div>
    <?php
    return ob_get_clean();
}
add_shortcode('hermes_words', 'hermes_word_counter_shortcode');


// ============================================================
// 3. Quick SEO Score
// ============================================================
function hermes_quick_score_shortcode($atts) {
    $atts = shortcode_atts(['url' => ''], $atts);
    ob_start(); ?>
    <div class="hermes-tool" style="max-width:700px;margin:20px auto;padding:20px;background:#f8fafc;border-radius:12px;font-family:Arial,sans-serif">
        <h3 style="margin-top:0">Score SEO Rapide</h3>
        <p style="color:#666">Obtenez un score SEO sur 100 pour n'importe quelle page.</p>
        <form method="post">
            <input type="url" name="hermes_score_url" value="<?php echo esc_url($_POST['hermes_score_url'] ?? $atts['url']); ?>"
                   placeholder="https://www.example.com" required
                   style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;font-size:16px">
            <button type="submit" style="background:#1E88E5;color:#fff;border:none;padding:12px 32px;border-radius:6px;cursor:pointer;font-weight:600;margin-top:10px;font-size:16px">
                Analyser gratuitement
            </button>
        </form>

        <?php if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['hermes_score_url'])):
            $url = esc_url($_POST['hermes_score_url']);
            $response = wp_remote_get($url, ['timeout' => 15, 'user-agent' => 'Hermes-SEO-Bot/3.0']);

            if (!is_wp_error($response) && wp_remote_retrieve_response_code($response) === 200):
                $html = wp_remote_retrieve_body($response);
                $score = 0;
                $checks = [];

                // Title
                preg_match('/<title>([^<]*)<\/title>/i', $html, $title_m);
                $title = $title_m[1] ?? '';
                $title_len = strlen($title);
                $checks[] = $title ? ['Title', $title_len >= 30 && $title_len <= 65, $title_len . ' chars'] : ['Title', false, 'Manquant'];

                // Meta description
                preg_match('/<meta[^>]+name="description"[^>]+content="([^"]*)"/i', $html, $desc_m);
                $desc = $desc_m[1] ?? '';
                $desc_len = strlen($desc);
                $checks[] = $desc ? ['Meta Description', $desc_len >= 70 && $desc_len <= 160, $desc_len . ' chars'] : ['Meta Description', false, 'Manquante'];

                // H1
                preg_match_all('/<h1[^>]*>([^<]*)<\/h1>/i', $html, $h1s);
                $h1_count = count($h1s[1]);
                $checks[] = $h1_count === 1 ? ['H1', true, '1 trouve'] : ['H1', false, $h1_count . ' trouves'];

                // HTTPS
                $is_https = strpos($url, 'https://') === 0;
                $checks[] = ['HTTPS', $is_https, $is_https ? 'OK' : 'Non'];

                // Viewport
                $has_viewport = preg_match('/<meta[^>]+name="viewport"/i', $html);
                $checks[] = ['Mobile (Viewport)', (bool)$has_viewport, $has_viewport ? 'OK' : 'Manquant'];

                // Schema.org
                $has_schema = preg_match('/application\/ld\+json/i', $html) || preg_match('/itemscope/i', $html);
                $checks[] = ['Schema.org', (bool)$has_schema, $has_schema ? 'Present' : 'Absent'];

                $score = round(array_sum(array_column($checks, 1)) / count($checks) * 100);
                $grade = $score >= 90 ? 'A' : ($score >= 70 ? 'B' : ($score >= 50 ? 'C' : ($score >= 30 ? 'D' : 'F')));
        ?>
            <div style="margin-top:20px;padding:20px;background:linear-gradient(135deg,#e8f5e9,#e3f2fd);border-radius:12px;text-align:center">
                <div style="font-size:4rem;font-weight:700;color:<?php echo $score >= 70 ? '#2e7d32' : ($score >= 40 ? '#e65100' : '#c62828'); ?>"><?php echo $score; ?>/100</div>
                <div style="font-size:1.2rem;font-weight:600">Note: <?php echo $grade; ?></div>
            </div>
            <table style="width:100%;margin-top:15px;border-collapse:collapse">
                <tr style="background:#1565c0;color:#fff"><th style="padding:8px;text-align:left">Critere</th><th style="padding:8px">Statut</th><th style="padding:8px">Detail</th></tr>
                <?php foreach ($checks as $c): ?>
                <tr style="border-bottom:1px solid #e2e8f0">
                    <td style="padding:8px"><?php echo $c[0]; ?></td>
                    <td style="padding:8px;text-align:center"><?php echo $c[1] ? '✅' : '❌'; ?></td>
                    <td style="padding:8px;font-size:13px"><?php echo $c[2]; ?></td>
                </tr>
                <?php endforeach; ?>
            </table>
            <?php else: ?>
                <p style="color:#c62828">Impossible d'acceder a l'URL. Verifiez que le site est accessible.</p>
            <?php endif; ?>
        <?php endif; ?>

        <p style="font-size:12px;color:#999;margin-top:20px;border-top:1px solid #eee;padding-top:10px">
            Score simplifie (6 criteres). <a href="/app/">Hermes SEO Pro</a> analyse 55+ signaux sur 7 dimensions.
        </p>
    </div>
    <?php
    return ob_get_clean();
}
add_shortcode('hermes_score', 'hermes_quick_score_shortcode');


// ============================================================
// 4. Master Shortcode — Route to any tool
// ============================================================
function hermes_tool_router_shortcode($atts) {
    $atts = shortcode_atts(['name' => 'serp'], $atts);
    switch ($atts['name']) {
        case 'words':
        case 'word_counter':
            return hermes_word_counter_shortcode();
        case 'score':
        case 'seo_score':
            return hermes_quick_score_shortcode($atts);
        case 'serp':
        case 'serp_preview':
        default:
            return hermes_serp_preview_shortcode($atts);
    }
}
add_shortcode('hermes_tool', 'hermes_tool_router_shortcode');


// ============================================================
// 5. Admin notice: Hermes SEO status
// ============================================================
function hermes_admin_notice() {
    $screen = get_current_screen();
    if ($screen && $screen->id === 'dashboard') {
        echo '<div class="notice notice-info is-dismissible"><p><strong>Hermes SEO</strong> est actif. Les outils gratuits sont disponibles via shortcodes. <a href="' . admin_url('admin.php?page=hermes-seo') . '">Configurer</a></p></div>';
    }
}
add_action('admin_notices', 'hermes_admin_notice');
