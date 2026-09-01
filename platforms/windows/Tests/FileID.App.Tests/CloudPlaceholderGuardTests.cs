using FileID.Services;
using Xunit;

namespace FileID.App.Tests;

public sealed class CloudPlaceholderGuardTests
{
    [Theory]
    [InlineData(0x0000_1000)]
    [InlineData(0x0004_0000)]
    [InlineData(0x0010_0000)]
    [InlineData(0x0040_0000)]
    public void Unavailable_cloud_attributes_are_always_skipped(int attributes)
    {
        Assert.True(ThumbnailService.CloudAttributesRequireSkip(attributes, false));
    }

    [Fact]
    public void Transitioning_onedrive_reparse_point_is_skipped_unless_pinned()
    {
        Assert.True(ThumbnailService.CloudAttributesRequireSkip(0x0000_0400, true));
        Assert.False(ThumbnailService.CloudAttributesRequireSkip(0x0000_0400 | 0x0008_0000, true));
        Assert.False(ThumbnailService.CloudAttributesRequireSkip(0x0000_0400, false));
    }
}
