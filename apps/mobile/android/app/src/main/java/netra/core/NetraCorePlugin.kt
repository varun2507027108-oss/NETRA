package netra.core

import android.content.Context
import android.os.Handler
import android.os.Looper
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import org.json.JSONObject
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/**
 * NETRA platform channel — the ONLY seam between Flutter and netra_core.
 *
 * Law (docs/BRIDGE_CONTRACT.md v1.2.4):
 *  - channel name "netra.core"; methods: ping, configure, scan,
 *    attach_signature, sync_now, queue_status
 *  - arguments AND returns are JSON-encoded STRINGS — this class is a
 *    faithful pipe: it does not read, rewrite, or derive anything from
 *    the payloads. Zero statutory logic in Kotlin.
 *  - errors travel IN-BAND (contract section 9); a channel-level failure
 *    (Python not started, module missing) returns an INTERNAL error
 *    envelope, never a crash.
 *  - result callbacks post back to the MAIN thread (Flutter
 *    requirement); all Python runs on a single background executor.
 */
object NetraCorePlugin {
    const val CHANNEL = "netra.core"

    private val executor: ExecutorService = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())
    private var cfg: String? = null

    fun register(context: Context, messenger: BinaryMessenger) {
        // Chaquopy must be started once before the first Python call, and
        // configure() must pin the evidence directory (ledger + dossiers)
        // to app-internal storage BEFORE the first scan (contract §2).
        val appContext = context.applicationContext
        executor.execute {
            try {
                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(appContext))
                }
                val api = Python.getInstance()
                    .getModule("netra_core.bridge.chaquopy_api")
                val cfg = JSONObject()
                    .put("data_dir", appContext.filesDir.absolutePath)
                    .toString()
                api.callAttr("configure", cfg)
            } catch (_: Exception) {
                // Not fatal at startup: the first scan surfaces the error
                // in-band; the UI still loads.
            }
        }
        MethodChannel(messenger, CHANNEL).setMethodCallHandler { call, result ->
            executor.execute { handle(call, result) }
        }
    }

    private fun handle(call: MethodCall, result: MethodChannel.Result) {
        val response: String = try {
            val api = Python.getInstance()
                .getModule("netra_core.bridge.chaquopy_api")
            when (call.method) {
                "ping" -> api.callAttr("ping").toString()
                "configure" -> api.callAttr("configure", argJson(call)).toString()
                "scan" -> api.callAttr("scan", argJson(call)).toString()
                "scan_tokens" ->
                    api.callAttr("scan_tokens", argJson(call)).toString()
                "attach_signature" ->
                    api.callAttr("attach_signature", argJson(call)).toString()
                "sync_now" -> api.callAttr("sync_now").toString()
                "queue_status" -> api.callAttr("queue_status").toString()
                "vision_config" ->
                    api.callAttr("vision_config").toString()
                "vision_prepass" -> {
                    // config fetched once from the Python core (the law)
                    if (cfg == null) {
                        cfg = api.callAttr("vision_config").toString()
                        NetraVision.loadConfig(cfg!!)
                    }
                    val args = JSONObject(argJson(call))
                    val resp = NetraVision.prepass(
                        args.getString("image_b64"),
                        args.optJSONObject("options")?.toString() ?: "{}"
                    )
                    android.util.Log.i("NetraVision", resp)
                    resp
                }
                "get_dossier" ->
                    api.callAttr("get_dossier", argJson(call)).toString()
                "sign_and_attach" -> {
                    // Dart sends the scan-result JSON; Kotlin builds the
                    // KeyStore signature request and files it in one step.
                    val attachReq = NetraKeystore.attachRequestFor(argJson(call))
                    api.callAttr("attach_signature", attachReq).toString()
                }
                "smoke" -> Python.getInstance()      // dev-only, not in the contract
                    .getModule("netra_smoke").callAttr("run").toString()
                else -> {
                    main.post { result.notImplemented() }
                    return
                }
            }
        } catch (e: Exception) {
            internalError(e)
        }
        main.post { result.success(response) }
    }

    private fun argJson(call: MethodCall): String {
        val arg = call.arguments<Any>()
        require(arg is String) {
            "netra.core ${call.method}: argument must be a JSON-encoded " +
                "string (contract §1) — got ${arg?.javaClass?.simpleName}"
        }
        return arg
    }

    private fun internalError(e: Exception): String =
        JSONObject()
            .put(
                "error",
                JSONObject()
                    .put("code", "INTERNAL")
                    .put("message", "${e.javaClass.simpleName}: ${e.message}"))
            .toString()
}
