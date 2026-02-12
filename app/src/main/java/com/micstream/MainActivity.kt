package com.micstream

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity(), MicStreamService.StatusListener {

    private lateinit var hostInput: EditText
    private lateinit var portInput: EditText
    private lateinit var toggleButton: Button
    private lateinit var statusText: TextView
    private lateinit var statusDot: View
    private lateinit var touchpadView: TouchpadView

    private var service: MicStreamService? = null
    private var bound = false
    private var touchSender: RemoteTouchSender? = null

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
            service = (binder as MicStreamService.LocalBinder).getService()
            service?.statusListener = this@MainActivity
            bound = true
            updateUI()
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            service?.statusListener = null
            service = null
            bound = false
            updateUI()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Hide action bar for more space
        supportActionBar?.hide()

        hostInput = findViewById(R.id.hostInput)
        portInput = findViewById(R.id.portInput)
        toggleButton = findViewById(R.id.toggleButton)
        statusText = findViewById(R.id.statusText)
        statusDot = findViewById(R.id.statusDot)
        touchpadView = findViewById(R.id.touchpadView)

        toggleButton.setOnClickListener {
            if (service?.isStreaming == true) {
                stopStream()
            } else {
                if (checkPermissions()) {
                    startStream()
                }
            }
        }

        // Initialize touch sender
        initTouchSender()

        // Button handlers
        findViewById<Button>(R.id.btnScrollUp).setOnClickListener {
            touchSender?.swipe(512, 500, 512, 250, 12)
        }
        findViewById<Button>(R.id.btnScrollDown).setOnClickListener {
            touchSender?.swipe(512, 250, 512, 500, 12)
        }
        findViewById<Button>(R.id.btnHome).setOnClickListener {
            // Tap the home area (bottom-center of AA screen)
            touchSender?.tap(512, 740)
        }
        findViewById<Button>(R.id.btnBack).setOnClickListener {
            // Tap back area (bottom-left of AA screen)
            touchSender?.tap(50, 740)
        }
    }

    private fun initTouchSender() {
        val host = hostInput.text.toString().ifBlank { "192.168.254.1" }
        val cm = getSystemService(ConnectivityManager::class.java)
        touchSender?.close()
        touchSender = RemoteTouchSender(host, 8001, cm)
        touchSender?.onStatusChanged = { msg ->
            runOnUiThread { statusText.text = "Touch: $msg" }
        }
        touchpadView.sender = touchSender
    }

    override fun onStart() {
        super.onStart()
        Intent(this, MicStreamService::class.java).also { intent ->
            bindService(intent, connection, Context.BIND_AUTO_CREATE)
        }
    }

    override fun onStop() {
        super.onStop()
        if (bound) {
            service?.statusListener = null
            unbindService(connection)
            bound = false
        }
    }

    override fun onDestroy() {
        touchSender?.close()
        super.onDestroy()
    }

    private fun startStream() {
        val host = hostInput.text.toString().ifBlank { "192.168.254.1" }
        val port = portInput.text.toString().toIntOrNull() ?: 8000

        val intent = Intent(this, MicStreamService::class.java).apply {
            putExtra(MicStreamService.EXTRA_HOST, host)
            putExtra(MicStreamService.EXTRA_PORT, port)
        }
        ContextCompat.startForegroundService(this, intent)

        Intent(this, MicStreamService::class.java).also {
            bindService(it, connection, Context.BIND_AUTO_CREATE)
        }

        // Reinit touch sender if host changed
        val currentHost = touchSender?.let { host } ?: ""
        if (currentHost != host) {
            touchSender?.close()
            initTouchSender()
        }
    }

    private fun stopStream() {
        service?.statusListener = null
        if (bound) {
            unbindService(connection)
            bound = false
        }
        stopService(Intent(this, MicStreamService::class.java))
        service = null
        statusText.text = "Stopped"
        statusDot.setBackgroundColor(0xFFFF5555.toInt())
        toggleButton.text = "Mic Start"
        hostInput.isEnabled = true
        portInput.isEnabled = true
    }

    private fun checkPermissions(): Boolean {
        val perms = mutableListOf(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            perms.add(Manifest.permission.POST_NOTIFICATIONS)
        }

        val needed = perms.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }

        if (needed.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, needed.toTypedArray(), 1)
            return false
        }
        return true
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 1 && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
            startStream()
        } else {
            statusText.text = "Mic permission required"
        }
    }

    override fun onStatusChanged(connected: Boolean, message: String) {
        statusText.text = message
        statusDot.setBackgroundColor(
            if (connected) 0xFF55FF55.toInt() else 0xFFFF5555.toInt()
        )
        updateUI()
    }

    private fun updateUI() {
        val streaming = service?.isStreaming == true
        toggleButton.text = if (streaming) "Mic Stop" else "Mic Start"
        hostInput.isEnabled = !streaming
        portInput.isEnabled = !streaming
    }
}
