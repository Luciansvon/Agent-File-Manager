using System.Text;

namespace FolderVision.Core;

internal sealed class BoundedLineReader
{
    public const int DefaultMaxChars = 64 * 1024 * 1024;

    private readonly int _maxChars;
    private readonly StringBuilder _buffer = new();
    private readonly char[] _chunk = new char[16 * 1024];
    private int _scanned;
    private bool _resyncing;

    public BoundedLineReader(int maxChars = DefaultMaxChars)
    {
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(maxChars);
        _maxChars = maxChars;
    }

    public async ValueTask<string?> ReadLineAsync(StreamReader reader, CancellationToken cancellationToken)
    {
        while (true)
        {
            var newline = -1;
            for (var i = _scanned; i < _buffer.Length; i++)
            {
                if (_buffer[i] == '\n')
                {
                    newline = i;
                    break;
                }
            }

            if (newline >= 0)
            {
                if (newline > _maxChars)
                {
                    _buffer.Remove(0, newline + 1);
                    _scanned = 0;
                    _resyncing = false;
                    throw new InvalidDataException($"IPC frame exceeded {_maxChars} characters.");
                }
                var line = _buffer.ToString(0, newline);
                _buffer.Remove(0, newline + 1);
                _scanned = 0;
                if (_resyncing)
                {
                    _resyncing = false;
                    continue;
                }
                if (line.Length > 0 && line[^1] == '\r') line = line[..^1];
                return line;
            }

            _scanned = _buffer.Length;
            if (_buffer.Length > _maxChars)
            {
                _buffer.Clear();
                _scanned = 0;
                _resyncing = true;
                throw new InvalidDataException($"IPC frame exceeded {_maxChars} characters.");
            }

            var before = _buffer.Length;
            var read = await reader.ReadAsync(_chunk.AsMemory(), cancellationToken).ConfigureAwait(false);
            if (read == 0)
            {
                if (!_resyncing && _buffer.Length > 0)
                {
                    var tail = _buffer.ToString();
                    _buffer.Clear();
                    _scanned = 0;
                    if (tail.Length > 0 && tail[^1] == '\r') tail = tail[..^1];
                    return tail;
                }
                return null;
            }

            _buffer.Append(_chunk, 0, read);
            _scanned = Array.IndexOf(_chunk, '\n', 0, read) >= 0 ? before : _buffer.Length;
        }
    }
}
