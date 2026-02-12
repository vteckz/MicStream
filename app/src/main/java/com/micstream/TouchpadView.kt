package com.micstream

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View

class TouchpadView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    var sender: RemoteTouchSender? = null

    private val bgPaint = Paint().apply {
        color = Color.parseColor("#1a1a2e")
        style = Paint.Style.FILL
    }
    private val borderPaint = Paint().apply {
        color = Color.parseColor("#4a4a6a")
        style = Paint.Style.STROKE
        strokeWidth = 3f
    }
    private val dotPaint = Paint().apply {
        color = Color.parseColor("#6c63ff")
        style = Paint.Style.FILL
    }
    private val crossPaint = Paint().apply {
        color = Color.parseColor("#2a2a4a")
        style = Paint.Style.STROKE
        strokeWidth = 1f
    }
    private val hintPaint = Paint().apply {
        color = Color.parseColor("#444466")
        textSize = 36f
        textAlign = Paint.Align.CENTER
        isAntiAlias = true
    }

    private var touchX = -1f
    private var touchY = -1f
    private var touching = false
    private val rect = RectF()

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        rect.set(0f, 0f, width.toFloat(), height.toFloat())

        // Background
        canvas.drawRoundRect(rect, 12f, 12f, bgPaint)
        canvas.drawRoundRect(rect, 12f, 12f, borderPaint)

        // Grid crosshairs
        val cx = width / 2f
        val cy = height / 2f
        canvas.drawLine(cx, 0f, cx, height.toFloat(), crossPaint)
        canvas.drawLine(0f, cy, width.toFloat(), cy, crossPaint)

        if (touching) {
            // Touch indicator
            canvas.drawCircle(touchX, touchY, 24f, dotPaint)
        } else {
            canvas.drawText("Touch to control AA", cx, cy - 10f, hintPaint)
            hintPaint.textSize = 24f
            canvas.drawText("Absolute: position maps to screen", cx, cy + 30f, hintPaint)
            hintPaint.textSize = 36f
        }
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        val s = sender ?: return true

        // Map touch position to screen coordinates (absolute mapping)
        val sx = ((event.x / width) * RemoteTouchSender.SCREEN_W).toInt()
            .coerceIn(0, RemoteTouchSender.SCREEN_W - 1)
        val sy = ((event.y / height) * RemoteTouchSender.SCREEN_H).toInt()
            .coerceIn(0, RemoteTouchSender.SCREEN_H - 1)

        touchX = event.x
        touchY = event.y

        when (event.action) {
            MotionEvent.ACTION_DOWN -> {
                touching = true
                s.send(RemoteTouchSender.CMD_DOWN, sx, sy)
            }
            MotionEvent.ACTION_MOVE -> {
                s.send(RemoteTouchSender.CMD_MOVE, sx, sy)
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                touching = false
                s.send(RemoteTouchSender.CMD_UP, sx, sy)
            }
        }
        invalidate()
        return true
    }
}
