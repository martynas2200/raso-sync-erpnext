-- ie.usp_SyncDataExport_i
CREATE PROC [ie].[usp_SyncDataExport_i]
    @DataType smallint,
    @DataProvider varchar(80),
    @ShopNo varchar(20),
    @SyncData nvarchar(MAX)
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare
	@vTC int = @@TRANCOUNT,
    @SyncDataExportId int,
	@RecDate datetime = GetDate(),
	@EditDate datetime = GetDate()
BEGIN TRY

	BEGIN TRAN

		INSERT INTO [ie].[SyncDataExport] ([DataType], [DataProvider], [ShopNo], [SyncData], [Status], [RecDate], [EditDate])
		SELECT @DataType, @DataProvider, @ShopNo, @SyncData, 0, @RecDate, @EditDate
		SELECT @SyncDataExportId = SCOPE_IDENTITY()
	COMMIT
	--EXEC [ie].[usp_SyncDataExport_v] @SyncDataExportId
	RETURN @SyncDataExportId
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);

	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ie.usp_SyncDataExport_iu
CREATE PROC [ie].[usp_SyncDataExport_iu]
    @SyncDataExportId int,
    @DataType smallint,
    @DataProvider varchar(80),
    @ShopNo varchar(20),
    @SyncData nvarchar(MAX),
    @Status smallint
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare
	@vTC int = @@TRANCOUNT,
	@RecDate datetime = GetDate(),
	@EditDate datetime = GetDate()
BEGIN TRY

	BEGIN TRAN

	IF (@SyncDataExportId IS NULL OR @SyncDataExportId = 0)
	BEGIN
		INSERT INTO [ie].[SyncDataExport] ([DataType], [DataProvider], [ShopNo], [SyncData], [Status], [RecDate], [EditDate])
		SELECT @DataType, @DataProvider, @ShopNo, @SyncData, @Status, @RecDate, @EditDate
		SELECT @SyncDataExportId = SCOPE_IDENTITY()

	END
	ELSE
	BEGIN
		UPDATE [ie].[SyncDataExport]
		SET    [DataType] = @DataType, [DataProvider] = @DataProvider, [ShopNo] = @ShopNo,
			[SyncData] = @SyncData, [Status] = @Status, [RecDate] = @RecDate, [EditDate] = @EditDate
		WHERE  [SyncDataExportId] = @SyncDataExportId
	END
	COMMIT
	EXEC [ie].[usp_SyncDataExport_v] @SyncDataExportId
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);

	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ie.usp_SyncDataExport_rp
CREATE PROC [ie].[usp_SyncDataExport_rp]
    @DateFrom datetime = NULL,
	@DateTo datetime = NULL,
	@DataType smallint = NULL,
	@DataProvider varchar(80) = NULL,
	@Status smallint = NULL,
	@DataString varchar(80) = NULL
AS
	SET NOCOUNT ON
	SET XACT_ABORT ON
	IF @DateFrom IS NULL SELECT @DateFrom = '1900-01-01'
	IF @DateTo IS NULL SELECT @DateTo = '2999-12-31'

	SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED
	SELECT --*
		[SyncDataExportId], [DataType], [DataProvider], (SUBSTRING([SyncData], 0, 252) + '...') as SyncData, [ShopNo], [StatusMsg], [Status], [RecDate], [EditDate]
	FROM   [ie].[SyncDataExport]
	WHERE  ([RecDate] >= @DateFrom	AND [RecDate] <= @DateTo)
	AND (@DataType IS NULL OR [DataType] = @DataType)
	AND (@DataProvider IS NULL OR [DataProvider] = @DataProvider)
	AND (@Status IS NULL OR [Status] = @Status)
	AND (@DataString IS NULL OR [SyncData] like '%' + @DataString + '%')

GO
-- ie.usp_SyncDataExport_u
CREATE PROC [ie].[usp_SyncDataExport_u]
    @SyncDataExportId int,
    @Status smallint,
	@StatusMsg VARCHAR(1024) = NULL
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare
	@vTC int = @@TRANCOUNT,
	@EditDate datetime = GetDate()
BEGIN TRY

	BEGIN TRAN

		UPDATE [ie].[SyncDataExport]
		SET    [Status] = @Status, [StatusMsg] = @StatusMsg, [EditDate] = @EditDate
		WHERE  [SyncDataExportId] = @SyncDataExportId
	COMMIT
	EXEC [ie].[usp_SyncDataExport_v] @SyncDataExportId
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);

	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ie.usp_SyncDataExport_v
CREATE PROC [ie].[usp_SyncDataExport_v]
    @SyncDataExportId int = NULL,
	@DataType smallint = NULL,
	@DataProvider varchar(80) = NULL,
	@Status smallint = NULL
AS
	SET NOCOUNT ON
	SET XACT_ABORT ON
	SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED
	IF ( @SyncDataExportId IS NOT NULL )
		SELECT *
			--[SyncDataExportId], [DataType], [DataProvider], [SyncData], [Status], [RecDate], [EditDate]
		FROM   [ie].[SyncDataExport]
		WHERE  ([SyncDataExportId] = @SyncDataExportId)
	ELSE
		SELECT *
			--[SyncDataExportId], [DataType], [DataProvider], [SyncData], [Status], [RecDate], [EditDate]
		FROM   [ie].[SyncDataExport]
		WHERE  (@DataType IS NULL OR [DataType] = @DataType )
		AND (@DataProvider IS NULL OR [DataProvider] = @DataProvider )
		AND (@Status IS NULL OR [Status] = @Status )
GO
-- ie.usp_SyncDataImport_group
CREATE PROC [ie].[usp_SyncDataImport_group]
    @GroupId bigint,
	@DataType smallint,
	@Status smallint
AS
	SET NOCOUNT ON
	SET XACT_ABORT ON
	SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED
	SELECT
			SyncDataImportId, DataType, DataProvider, Status, StatusMsg, RecDate, EditDate, GroupId, GroupNo, GroupState
		FROM   [ie].[SyncDataImport] a
		WHERE  [GroupId] = @GroupId
		AND [DataType] = @DataType
		AND [Status] = @Status
		ORDER BY [SyncDataImportId]
GO
-- ie.usp_SyncDataImport_i
CREATE PROC [ie].[usp_SyncDataImport_i]
    @DataType smallint,
    @DataProvider varchar(80),
    @SyncData nvarchar(MAX),
	@GroupId bigint = NULL,
	@GroupNo integer = NULL,
	@GroupState smallint = NULL
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare
	@vTC int = @@TRANCOUNT,
    @SyncDataImportId int,
	@RecDate datetime = GetDate(),
	@EditDate datetime = GetDate()
BEGIN TRY

	BEGIN TRAN

		INSERT INTO [ie].[SyncDataImport] ([DataType], [DataProvider], [SyncData], [GroupId], [GroupNo], [GroupState], [Status], [RecDate], [EditDate])
		SELECT @DataType, @DataProvider, @SyncData, @GroupId, @GroupNo, @GroupState, 0, @RecDate, @EditDate
		SELECT @SyncDataImportId = SCOPE_IDENTITY()
	COMMIT
	EXEC [ie].[usp_SyncDataImport_v] @SyncDataImportId
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);

	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ie.usp_SyncDataImport_iu
CREATE PROC [ie].[usp_SyncDataImport_iu]
    @SyncDataImportId int,
    @DataType smallint,
    @DataProvider varchar(80),
    @SyncData nvarchar(MAX),
    @Status smallint,
	@GroupId bigint = NULL,
	@GroupNo integer = NULL,
	@GroupState smallint = NULL
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare
	@vTC int = @@TRANCOUNT,
	@RecDate datetime = GetDate(),
	@EditDate datetime = GetDate()
BEGIN TRY

	BEGIN TRAN

	IF (@SyncDataImportId IS NULL OR @SyncDataImportId = 0)
	BEGIN
		INSERT INTO [ie].[SyncDataImport] ([DataType], [DataProvider], [SyncData], [GroupId], [GroupNo], [GroupState], [Status], [RecDate], [EditDate])
		SELECT @DataType, @DataProvider, @SyncData, @GroupId, @GroupNo, @GroupState, @Status, @RecDate, @EditDate
		SELECT @SyncDataImportId = SCOPE_IDENTITY()

	END
	ELSE
	BEGIN
		UPDATE [ie].[SyncDataImport]
		SET    [DataType] = @DataType, [DataProvider] = @DataProvider, [SyncData] = @SyncData, [GroupId] = @GroupId, [GroupNo] = @GroupNo, [GroupState] = @GroupState, [Status] = @Status, [EditDate] = @EditDate
		WHERE  [SyncDataImportId] = @SyncDataImportId
	END
	COMMIT
	EXEC [ie].[usp_SyncDataImport_v] @SyncDataImportId
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);

	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ie.usp_SyncDataImport_rp
CREATE PROC [ie].[usp_SyncDataImport_rp]
    @DateFrom datetime = NULL,
	@DateTo datetime = NULL,
	@DataType smallint = NULL,
	@DataProvider varchar(80) = NULL,
	@Status smallint = NULL,
	@DataString varchar(80) = NULL
AS
	SET NOCOUNT ON
	SET XACT_ABORT ON
	IF @DateFrom IS NULL SELECT @DateFrom = '1900-01-01'
	IF @DateTo IS NULL SELECT @DateTo = '2999-12-31'

	SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED
	SELECT --*
		[SyncDataImportId], [DataType], [DataProvider], (SUBSTRING([SyncData], 0, 252) + '...') as SyncData, [GroupId], [GroupNo], [GroupState], [StatusMsg], [Status], [RecDate], [EditDate]
	FROM   [ie].[SyncDataImport]
	WHERE  ([RecDate] >= @DateFrom	AND [RecDate] <= @DateTo)
	AND (@DataType IS NULL OR [DataType] = @DataType)
	AND (@DataProvider IS NULL OR [DataProvider] = @DataProvider)
	AND (@Status IS NULL OR [Status] = @Status)
	AND (@DataString IS NULL OR [SyncData] like '%' + @DataString + '%')

GO
-- ie.usp_SyncDataImport_u
CREATE PROC [ie].[usp_SyncDataImport_u]
    @SyncDataImportId int = NULL,
    @Status smallint,
	@StatusMsg VARCHAR(1024) = NULL,
	@GroupId bigint = NULL,
	@DataType smallint = NULL
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare
	@vTC int = @@TRANCOUNT,
	@EditDate datetime = GetDate()
BEGIN TRY

	BEGIN TRAN

		IF (@SyncDataImportId IS NOT NULL AND @SyncDataImportId > 0)
			UPDATE [ie].[SyncDataImport]
			SET    [Status] = @Status, [StatusMsg] = @StatusMsg, [EditDate] = @EditDate
			WHERE  [SyncDataImportId] = @SyncDataImportId
		ELSE
			UPDATE [ie].[SyncDataImport]
			SET    [Status] = @Status, [StatusMsg] = @StatusMsg, [EditDate] = @EditDate
			WHERE  [GroupId] = @GroupId AND DataType = @DataType -- RRR - 2022-03-04 - AND DataType = @DataType
	COMMIT
	--EXEC [ie].[usp_SyncDataImport_v] @SyncDataImportId
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);

	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ie.usp_SyncDataImport_v
CREATE PROC [ie].[usp_SyncDataImport_v]
    @SyncDataImportId int = NULL,
	@DataType smallint = NULL,
	@DataProvider varchar(80) = NULL,
	@Status smallint = NULL,
	@OnlyTop smallint = NULL
AS
	SET NOCOUNT ON
	SET XACT_ABORT ON
	SELECT @OnlyTop = ISNULL(@OnlyTop, 0)

	SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED
	IF ( @SyncDataImportId IS NOT NULL )
		SELECT *
			--[SyncDataImportId], [DataType], [DataProvider], [SyncData], [Status], [RecDate], [EditDate]
		FROM   [ie].[SyncDataImport]
		WHERE  ([SyncDataImportId] = @SyncDataImportId)
	ELSE
	IF ( @OnlyTop > 0 )
		SELECT TOP 100 *
			--[SyncDataImportId], [DataType], [DataProvider], [SyncData], [Status], [RecDate], [EditDate]
		FROM   [ie].[SyncDataImport] a
		WHERE  (@DataType IS NULL OR [DataType] = @DataType )
		AND (@DataProvider IS NULL OR [DataProvider] = @DataProvider )
		AND (@Status IS NULL OR [Status] = @Status )
		AND
		(
			GroupNo IS NULL OR EXISTS(SELECT 1 FROM [ie].[SyncDataImport] b WHERE a.GroupId = b.GroupId AND b.GroupState = 1)
		)
		ORDER BY [SyncDataImportId]
	ELSE
		SELECT *
			--[SyncDataImportId], [DataType], [DataProvider], [SyncData], [Status], [RecDate], [EditDate]
		FROM   [ie].[SyncDataImport] a
		WHERE  (@DataType IS NULL OR [DataType] = @DataType )
		AND (@DataProvider IS NULL OR [DataProvider] = @DataProvider )
		AND (@Status IS NULL OR [Status] = @Status )
		AND
		(
			GroupNo IS NULL OR EXISTS(SELECT 1 FROM [ie].[SyncDataImport] b WHERE a.GroupId = b.GroupId AND b.GroupState = 1)
		)
		ORDER BY [SyncDataImportId]
GO
-- ie.usp_SyncDataImport_vg
CREATE PROC [ie].[usp_SyncDataImport_vg]
    @SyncDataImportId int = NULL,
	@DataType smallint = NULL,
	@DataProvider varchar(80) = NULL,
	@Status smallint = NULL,
	@OnlyTop smallint = NULL
AS
	SET NOCOUNT ON
	SET XACT_ABORT ON
	SELECT @OnlyTop = ISNULL(@OnlyTop, 0)

	SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED
	IF ( @SyncDataImportId IS NOT NULL )
		SELECT
			SyncDataImportId, DataType, DataProvider, Status, StatusMsg, RecDate, EditDate, GroupId, GroupNo, GroupState
		FROM   [ie].[SyncDataImport]
		WHERE  ([SyncDataImportId] = @SyncDataImportId)
	ELSE
	IF ( @OnlyTop > 0 )
		SELECT TOP 100
			SyncDataImportId, DataType, DataProvider, Status, StatusMsg, RecDate, EditDate, GroupId, GroupNo, GroupState
		FROM   [ie].[SyncDataImport] a
		WHERE  (@DataType IS NULL OR [DataType] = @DataType )
		AND (@DataProvider IS NULL OR [DataProvider] = @DataProvider )
		AND (@Status IS NULL OR [Status] = @Status )
		AND
		(
			GroupNo IS NULL OR EXISTS(SELECT 1 FROM [ie].[SyncDataImport] b WHERE a.GroupId = b.GroupId AND b.GroupState = 1)
		)
		ORDER BY [SyncDataImportId]
	ELSE
		SELECT
			SyncDataImportId, DataType, DataProvider, Status, StatusMsg, RecDate, EditDate, GroupId, GroupNo, GroupState
		FROM   [ie].[SyncDataImport] a
		WHERE  (@DataType IS NULL OR [DataType] = @DataType )
		AND (@DataProvider IS NULL OR [DataProvider] = @DataProvider )
		AND (@Status IS NULL OR [Status] = @Status )
		AND
		(
			GroupNo IS NULL OR EXISTS(SELECT 1 FROM [ie].[SyncDataImport] b WHERE a.GroupId = b.GroupId AND b.GroupState = 1)
		)
		ORDER BY [SyncDataImportId]
GO
-- ms.usp_AdMedia_delete
CREATE PROC [ms].[usp_AdMedia_delete]
	@SyncID varchar(50)
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare @vTC int = @@TRANCOUNT
BEGIN TRY
	BEGIN TRAN
	DELETE FROM [ms].[AdMedia_sync]
	WHERE SyncID = @SyncID
	COMMIT
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);
	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ms.usp_AdMedia_iu
CREATE PROC [ms].[usp_AdMedia_iu]
@AdMediaId bigint,
@AdMediaData varbinary(MAX),
@AdMediaName varchar(255),
@AdMediaType varchar(255),
@Enabled smallint = NULL,
@DurationMillisecond int = NULL,
@FilePath varchar(255)
AS
SET NOCOUNT ON
SET XACT_ABORT ON
DECLARE
@RecDate datetime = GetDate(),
@EditDate datetime = GetDate()
BEGIN TRY
BEGIN TRAN
IF (@AdMediaId IS NULL OR @AdMediaId = 0)
	BEGIN
		INSERT INTO ms.AdMedia (AdMediaData, AdMediaName, AdMediaType, EditDate, RecDate, Enabled, DurationMillisecond, FilePath)
		VALUES (@AdMediaData, @AdMediaName, @AdMediaType, @EditDate, @RecDate, @Enabled, @DurationMillisecond, @FilePath)
	END
	ELSE
	BEGIN
		UPDATE [ms].[AdMedia]
		SET    [AdMediaData] = @AdMediaData, [AdMediaName] = @AdMediaName, [AdMediaType] = @AdMediaType, [EditDate] = @EditDate, [DurationMillisecond] = @DurationMillisecond, [FilePath] = @FilePath
		WHERE  [AdMediaId] = @AdMediaId
	END
COMMIT
END TRY
BEGIN CATCH
DECLARE @ErrorMessage NVARCHAR(4000);
DECLARE @ErrorSeverity INT;
DECLARE @ErrorState INT;
SELECT
	@ErrorMessage = ERROR_MESSAGE(),
	@ErrorSeverity = ERROR_SEVERITY(),
	@ErrorState = ERROR_STATE();
RAISERROR (@ErrorMessage, -- Message text.
	@ErrorSeverity, -- Severity.
	@ErrorState -- State.
);
END CATCH
GO
-- ms.usp_AdMedia_sync
CREATE PROC [ms].[usp_AdMedia_sync]
    @LastSyncDate datetime = NULL,
    @LastId bigint = NULL,
    @RecCount int = NULL
AS
	SET NOCOUNT ON
	SET XACT_ABORT ON
	IF (@LastSyncDate IS NULL)
		SELECT @LastSyncDate = '1900.01.01'
	SELECT @LastId = ISNULL(@LastId, 0)
	SELECT TOP(CASE
		WHEN ISNULL(@RecCount,0) > 0 THEN @RecCount
		ELSE 1000000000 END) *
	FROM
	(
		SELECT  a.*
		FROM   ms.AdMedia a
		INNER JOIN ms.PlaylistsItems pli ON pli.AdMediaId = a.AdMediaId AND pli.Enabled = 1
		INNER JOIN ms.Playlists pl ON pl.PlaylistsId = pli.PlaylistsId AND ISNULL(pl.PlaylistValidToDate, CONVERT(date, GETDATE())) >= CONVERT(date, GETDATE())
		WHERE	(a.EditDate = @LastSyncDate) and a.AdMediaId > @LastId
		UNION
		SELECT  a.*
		FROM   ms.AdMedia a
		INNER JOIN ms.PlaylistsItems pli ON pli.AdMediaId = a.AdMediaId AND pli.Enabled = 1
		INNER JOIN ms.Playlists pl ON pl.PlaylistsId = pli.PlaylistsId AND ISNULL(pl.PlaylistValidToDate, CONVERT(date, GETDATE())) >= CONVERT(date, GETDATE())
		WHERE	(a.EditDate > @LastSyncDate)
	) a
	ORDER BY EditDate, AdMediaId
GO
-- ms.usp_AdMedia_update
CREATE PROC [ms].[usp_AdMedia_update]
	@SyncID varchar(50)
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare @vTC int = @@TRANCOUNT
BEGIN TRY
	SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED
	BEGIN TRAN
	SET IDENTITY_INSERT [ms].[AdMedia] ON;

	SELECT * INTO #TmpSync FROM [ms].[AdMedia_sync]
	WHERE SyncID = @SyncID
	merge into [ms].[AdMedia] as Target
	using #TmpSync as Source
	on Target.[AdMediaId] = Source.AdMediaId
	when matched then
	UPDATE SET
		Target.[AdMediaName] = Source.AdMediaName, Target.[AdMediaType] = Source.AdMediaType, Target.[RecDate] = Source.RecDate,
		Target.[EditDate] = Source.EditDate, Target.[Enabled] = Source.Enabled, Target.[AdMediaData] = Source.AdMediaData, Target.[DurationMillisecond] = Source.DurationMillisecond, Target.[FilePath] = Source.FilePath
	when not matched then
	INSERT ([AdMediaId], [AdMediaName], [AdMediaType], [AdMediaData], [Enabled], [RecDate], [EditDate], [DurationMillisecond], [FilePath])
	VALUES (Source.AdMediaId, Source.AdMediaName, Source.AdMediaType, Source.AdMediaData, Source.Enabled, Source.RecDate, Source.EditDate, Source.DurationMillisecond, Source.FilePath);
	DELETE FROM [ms].[AdMedia_sync]
	WHERE SyncID = @SyncID
	COMMIT
	SET IDENTITY_INSERT [ms].[AdMedia] OFF;
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);
	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ms.usp_AdMedia_v
CREATE PROC [ms].[usp_AdMedia_v]
@AdMediaId bigint = NULL
AS
SET NOCOUNT ON
SET XACT_ABORT ON
SELECT
    a.AdMediaId,
    a.AdMediaType,
    a.Enabled,
    a.RecDate,
    a.EditDate,
    a.AdMediaName + '.' + a.AdMediaType AS AdMediaName,
	a.DurationMillisecond,
	a.FilePath
FROM   [ms].[AdMedia] a
WHERE
	(a.[AdMediaId] = @AdMediaId OR @AdMediaId IS NULL)
ORDER BY a.AdMediaName
GO
-- ms.usp_GoodsImages_d
CREATE PROC [ms].[usp_GoodsImages_d]
    @GoodsImagesId int
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare @vTC int = @@TRANCOUNT
BEGIN TRY

	BEGIN TRAN

	/*DELETE
	FROM   [ms].[GoodsImages]
	WHERE  [GoodsImagesId] = @GoodsImagesId*/
	UPDATE [ms].[GoodsImages]
	SET [Enabled] = 0, [EditDate] = GetDate()
	WHERE  [GoodsImagesId] = @GoodsImagesId
	COMMIT
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);

	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ms.usp_GoodsImages_delete
CREATE PROC [ms].[usp_GoodsImages_delete]
	@SyncID varchar(50)
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare @vTC int = @@TRANCOUNT
BEGIN TRY

	BEGIN TRAN

	DELETE FROM [ms].[GoodsImages_sync]
	WHERE SyncID = @SyncID

	COMMIT

END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);

	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ms.usp_GoodsImages_iu
CREATE PROC [ms].[usp_GoodsImages_iu]
    @GoodsImagesId int,
    @Code varchar(80),
    @Name varchar(80) = NULL,
    @Description nvarchar(512) = NULL,
    @ImageType smallint = NULL,
    @ImageData image = NULL,
    @Enabled smallint = NULL,
	@ImageLink varchar(MAX) = NULL
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare
	@vTC int = @@TRANCOUNT,
	@RecDate datetime = GetDate(),
	@EditDate datetime = GetDate()
--IF (@GoodsImagesId IS NULL OR @GoodsImagesId = 0)
--	SELECT @GoodsImagesId = MAX(GoodsImagesId) FROM [ms].[GoodsImages] WHERE Code = @Code
BEGIN TRY

	BEGIN TRAN

	IF (@GoodsImagesId IS NULL OR @GoodsImagesId = 0)
	BEGIN
		INSERT INTO [ms].[GoodsImages] ([Code], [Name], [Description], [ImageType], [ImageData], [RecDate], [EditDate], [Enabled], [ImageLink])
		SELECT @Code, @Name, @Description, @ImageType, @ImageData, @RecDate, @EditDate, @Enabled, @ImageLink
		SELECT @GoodsImagesId = SCOPE_IDENTITY()

	END
	ELSE
	BEGIN
		UPDATE [ms].[GoodsImages]
		SET    [Code] = @Code, [Name] = @Name, [Description] = @Description, [ImageType] = @ImageType, [ImageData] = @ImageData, [EditDate] = @EditDate, [Enabled] = @Enabled, [ImageLink] = @ImageLink
		WHERE  [GoodsImagesId] = @GoodsImagesId
	END
	-- Begin Return Select <- do not remove
	-- SELECT [GoodsImagesId], [Code], [ImageData], [RecDate], [EditDate], [Enabled]
	-- FROM   [ms].[GoodsImages]
	-- WHERE  [GoodsImagesId] = @GoodsImagesId
	EXEC [ms].[usp_GoodsImages_v] @GoodsImagesId
	-- End Return Select <- do not remove
	COMMIT
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);

	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ms.usp_GoodsImages_sync
CREATE PROC [ms].[usp_GoodsImages_sync]
    @LastSyncDate datetime = NULL,
    @LastId bigint = NULL,
    @RecCount int = NULL
AS
	SET NOCOUNT ON
	SET XACT_ABORT ON
	IF (@LastSyncDate IS NULL)
		SELECT @LastSyncDate = '1900.01.01'

	SELECT @LastId = ISNULL(@LastId, 0)

	SELECT TOP(CASE
		WHEN ISNULL(@RecCount,0) > 0 THEN @RecCount
		ELSE 1000000000 END) *
	FROM
	(
		SELECT  *	FROM   ms.GoodsImages
		WHERE	(EditDate = @LastSyncDate) and GoodsImagesId > @LastId
		UNION ALL
		SELECT  *	FROM   ms.GoodsImages
		WHERE	(EditDate > @LastSyncDate)
	) a
	ORDER BY EditDate, GoodsImagesId

GO
-- ms.usp_GoodsImages_update
CREATE PROC [ms].[usp_GoodsImages_update]
	@SyncID varchar(50)
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare @vTC int = @@TRANCOUNT, @vCount int = 0
BEGIN TRY

	SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED

	BEGIN TRAN

	-- ======================================================================================
    -- prasidubliuojancius irasus iskeliame i klaidu lentele ir istriname is importo lenteles
    SELECT a.* INTO #TmpErr FROM ms.GoodsImages_sync a
    WHERE a.SyncID = @SyncID AND a.GoodsImagesId NOT IN ( SELECT MAX(b.GoodsImagesId) FROM ms.GoodsImages_sync b WHERE a.Code = b.Code AND a.ImageType = b.ImageType GROUP BY b.Code, b.ImageType, b.SyncID )

    SELECT @vCount = (SELECT COUNT(1) FROM #TmpErr)
    --PRINT 'GoodsImages duplicated records: ' + CONVERT(varchar, @vCount) + ' - ' + CONVERT(varchar, GetDate(), 114)
    IF (@vCount > 0)
    BEGIN
        -- INSERT INTO [ms].[SyncDataErrors] ([TableName],[TableData],[SyncID])
        -- SELECT 'GoodsImages_sync', CONCAT(Code, '|', ImageType, '|', ImageLink, '...' ) , @SyncID
        -- FROM #TmpErr
        DELETE FROM ms.GoodsImages_sync
        WHERE GoodsImagesId IN (SELECT a.GoodsImagesId FROM #TmpErr a)
    END
    --PRINT 'GoodsImages duplicated saved: ' + CONVERT(varchar, @vCount) + ' - ' + CONVERT(varchar, GetDate(), 114)
    -- ======================================================================================

	SELECT * INTO #TmpSyncAll FROM [ms].[GoodsImages_sync]
	WHERE SyncID = @SyncID

	-- atrenkam tik pasikeitusius irasus
    SELECT s.* INTO #TmpSync
    FROM #TmpSyncAll s
    WHERE s.SyncId = @SyncID AND
        (
			(SELECT COUNT(*) FROM ms.GoodsImages t
			WHERE
				t.[Code] = s.[Code] AND
				ISNULL(t.[Name],'') = ISNULL(s.[Name],'') AND
				ISNULL(t.[Description],'') = ISNULL(s.[Description],'') AND
				ISNULL(t.[ImageType],0) = ISNULL(s.[ImageType],0) AND
				--t.[ImageData] = s.[ImageData] AND
				ISNULL(t.[Enabled],0) = ISNULL(s.[Enabled],0) AND
				ISNULL(t.[ImageLink],'') = ISNULL(s.[ImageLink],'')
			) = 0 OR
			s.[ImageData] IS NOT NULL
		)

	merge into [ms].[GoodsImages] as Target
	using #TmpSync as Source
	--on Target.[GoodsImagesId] = Source.GoodsImagesId
	on Target.[Code] = Source.Code and Target.[ImageType] = Source.ImageType
	when matched then
	UPDATE SET
		Target.[Code] = Source.Code, Target.[Name] = Source.Name, Target.[Description] = Source.Description, Target.[ImageType] = Source.ImageType, Target.[ImageData] = Source.ImageData, Target.[Enabled] = Source.Enabled, Target.[RecDate] = Source.RecDate, Target.[EditDate] = Source.EditDate, Target.[ImageLink] = Source.ImageLink
	when not matched then
	INSERT ([Code], [Name], [Description], [ImageType], [ImageData], [Enabled], [RecDate], [EditDate], [ImageLink])
	VALUES (Source.Code, Source.Name, Source.Description, Source.ImageType, Source.ImageData, Source.Enabled, Source.RecDate, Source.EditDate, Source.ImageLink);
	DELETE FROM [ms].[GoodsImages_sync]
	--WHERE [GoodsImagesId] IN ( SELECT [GoodsImagesId] FROM  #TmpSync )
	WHERE SyncID = @SyncID

	COMMIT
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);

	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ms.usp_GoodsImages_v
CREATE PROC [ms].[usp_GoodsImages_v]
    @GoodsImagesId int = NULL,
	@Code varchar(80) = NULL,
	@ImageType smallint = NULL
AS
	SET NOCOUNT ON
	SET XACT_ABORT ON
	--SELECT @ImageType = ISNULL(@ImageType, 0)

	SELECT *
		--[GoodsImagesId], [Code], [ImageData], [RecDate], [EditDate], [Enabled]
	FROM   [ms].[GoodsImages]
	WHERE
		([GoodsImagesId] = @GoodsImagesId OR @GoodsImagesId IS NULL)
		AND (@Code IS NULL OR [Code] = @Code)
		AND (@ImageType IS NULL OR ImageType = @ImageType)
GO
-- ms.usp_MSImg_del
CREATE PROC [ms].[usp_MSImg_del]
    @Date datetime = NULL,
	@ImpExpDays int = NULL,
	@LogDays int = NULL
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare
	@vTC int = @@TRANCOUNT,
	@LogDate datetime
BEGIN TRY
	/* 2022-10-20 - iskelta i DLL, nes konfiguracija yra ne IMG duombazeje, o pagrindineje RR DB
	-- '76', @Name = 'IMPORTAS/EKSPORTAS: kiek dienų saugomi importo/eksporto duomenys?'
	DECLARE @ImpExpDays int = 10
	SELECT @ImpExpDays = ValueInt FROM [ms].[ConfigValues] WHERE ConfigId = 1 and ConfigTypesId = 76
	SELECT @ImpExpDays = ISNULL(@ImpExpDays, 10)


	-- '8008', @Name = 'DataExchangeService LogFilesPeriod' - is settings.xml failo
	DECLARE @LogDays int = 14, @LogDate datetime, @vTopServer int = 0 --0-SHOP, >=1-TOP
	SELECT @vTopServer = COUNT(*) FROM [ms].[ConfigValues] where ConfigId = 3000 AND ConfigTypesId = 3001 AND RefID = 2
	IF (@vTopServer = 0)
		--SHOP serveris
		SELECT @LogDays = MAX(ValueInt) FROM [ms].[ConfigValues] WHERE ConfigId = 8000 and ConfigTypesId = 8008 AND RefID <> 2
	ELSE
		--TOP serveris
		SELECT @LogDays = MAX(ValueInt) FROM [ms].[ConfigValues] WHERE ConfigId = 8000 and ConfigTypesId = 8008 AND RefID = 2
	SELECT @LogDays = ISNULL(@LogDays, 14)
	*/
	SELECT
		@ImpExpDays = ISNULL(@ImpExpDays, 10),
		@LogDays = ISNULL(@LogDays, 14)

	-- jei data nenurodyta - tada imame dabartine data, minus kiek nurodyta konfiguracijoje
	SELECT @Date = ISNULL(@Date, DATEADD(D, -1 * @ImpExpDays, GetDate()))
	-- galutine data imame pagal LogFilesPeriod kintamaji
	SELECT @LogDate = DATEADD(D, -1 * @LogDays, GetDate())
	--print @Date
	--print @LogDate
	BEGIN TRAN

	-- panaikinam senus importuotus arba bandytus importuoti duomenis (Status >= 1) nurodytai datai (@Date)
	DELETE ie.SyncDataImport WHERE RecDate < @Date AND Status >= 1
	-- panaikinam senus, bet dar neimportuotus duomenis (Status = 0) nurodytai LogFilesPeriod datai (@LogDate)
	DELETE ie.SyncDataImport WHERE RecDate < @LogDate AND Status = 0
	-- panaikinam senus eksportuotus ir jau provaiderio bandytus paimti duomenis (Status >= 1) nurodytai datai (@Date)
	DELETE ie.SyncDataExport WHERE RecDate < @Date AND Status >= 1
	-- panaikinam senus, bet dar provaiderio nepaimtus duomenis (Status = 0) nurodytai LogFilesPeriod datai (@LogDate)
	DELETE ie.SyncDataExport WHERE RecDate < @LogDate AND Status = 0

	COMMIT
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ms.usp_MSImg_shrink
CREATE PROC [ms].[usp_MSImg_shrink]
	@DBName varchar(80)
AS
SET NOCOUNT ON
SET XACT_ABORT ON
DECLARE @DBSysName varchar(80) = @DBName, @DBLogName varchar(80) = @DBName + '_log'
BEGIN TRY

	EXECUTE('ALTER DATABASE ' + @DBName + ' SET RECOVERY SIMPLE');
	--DBCC SHRINKDATABASE (@DBName, TRUNCATEONLY);
	DBCC SHRINKDATABASE (@DBName, NOTRUNCATE);
	-- shrink DB file
	select @DBSysName = name from sys.database_files where type=0
	DBCC SHRINKFILE (@DBSysName);
	-- shrink LOG file
	select @DBLogName = name from sys.database_files where type=1
	DBCC SHRINKFILE (@DBLogName);
	EXECUTE('ALTER DATABASE ' + @DBName + ' SET RECOVERY FULL');
END TRY
BEGIN CATCH
  	EXECUTE('ALTER DATABASE ' + @DBName + ' SET RECOVERY FULL');
END CATCH
RETURN
GO
-- ms.usp_Playlists_delete
CREATE PROC [ms].[usp_Playlists_delete]
	@SyncID varchar(50)
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare @vTC int = @@TRANCOUNT
BEGIN TRY
	BEGIN TRAN
	DELETE FROM [ms].[Playlists_sync]
	WHERE SyncID = @SyncID
	COMMIT
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);
	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ms.usp_Playlists_sync
CREATE PROC [ms].[usp_Playlists_sync]
    @LastSyncDate datetime = NULL,
    @LastId bigint = NULL,
    @RecCount int = NULL
AS
	SET NOCOUNT ON
	SET XACT_ABORT ON
	IF (@LastSyncDate IS NULL)
		SELECT @LastSyncDate = '1900.01.01'
	SELECT @LastId = ISNULL(@LastId, 0)
	SELECT TOP(CASE
		WHEN ISNULL(@RecCount,0) > 0 THEN @RecCount
		ELSE 1000000000 END) *
	FROM
	(
		SELECT  *	FROM   ms.Playlists
		WHERE	(EditDate = @LastSyncDate) and Playlists.PlaylistsId > @LastId
		UNION
		SELECT  *	FROM   ms.Playlists
		WHERE	(EditDate > @LastSyncDate)
	) a
	ORDER BY EditDate, PlaylistsId
GO
-- ms.usp_Playlists_update
CREATE PROC [ms].[usp_Playlists_update]
	@SyncID varchar(50)
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare @vTC int = @@TRANCOUNT
BEGIN TRY
	SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED
	BEGIN TRAN
	SET IDENTITY_INSERT [ms].[Playlists] ON;
	SELECT * INTO #TmpSync FROM [ms].[Playlists_sync]
	WHERE SyncID = @SyncID
	merge into [ms].[Playlists] as Target
	using #TmpSync as Source
	on Target.[PlaylistsId] = Source.PlaylistsId
	when matched then
	UPDATE SET
		Target.[PlaylistName] = Source.PlaylistName, Target.[PlaylistValidFromDate] = Source.PlaylistValidFromDate,
		Target.[PlaylistValidToDate] = Source.PlaylistValidToDate, Target.[PlaylistValidFromTime] = Source.PlaylistValidFromTime,
		Target.[PlaylistValidToTime] = Source.PlaylistValidToTime, Target.[PlaylistActionOnInterrupt] = Source.PlaylistActionOnInterrupt,
		Target.[RecDate] = Source.RecDate, Target.[EditDate] = Source.EditDate, Target.[Enabled] = Source.Enabled, Target.[ShopNo] = Source.ShopNo, Target.[PosNo] = Source.PosNo,
		Target.[SplitScreen] = Source.SplitScreen,
		Target.[SplitScreenAdFirst] = Source.SplitScreenAdFirst,
		Target.[SplitScreenVerticalLayout] = Source.SplitScreenVerticalLayout,
		Target.[SplitScreenAdRatioPercent] = Source.SplitScreenAdRatioPercent
	when not matched then
	INSERT ([PlaylistsId], [PlaylistName], [PlaylistValidFromDate], [PlaylistValidToDate], [PlaylistValidFromTime], [PlaylistValidToTime], [PlaylistActionOnInterrupt], [Enabled],
	[RecDate], [EditDate], [ShopNo], [PosNo], [SplitScreen], [SplitScreenAdFirst], [SplitScreenVerticalLayout], [SplitScreenAdRatioPercent])
	VALUES (Source.PlaylistsId, Source.PlaylistName, Source.PlaylistValidFromDate, Source.PlaylistValidToDate, Source.PlaylistValidFromTime,
	Source.PlaylistValidToTime, Source.PlaylistActionOnInterrupt, Source.Enabled, Source.RecDate, Source.EditDate,
	Source.ShopNo, Source.PosNo, Source.SplitScreen, Source.SplitScreenAdFirst, Source.SplitScreenVerticalLayout, Source.SplitScreenAdRatioPercent);
	DELETE FROM [ms].[Playlists_sync]
	WHERE SyncID = @SyncID
	COMMIT
	SET IDENTITY_INSERT [ms].[Playlists] OFF;
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);
	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ms.usp_Playlists_v
CREATE PROC [ms].[usp_Playlists_v]
@PlaylistsId bigint = NULL
AS
SET NOCOUNT ON
SET XACT_ABORT ON
SELECT *
FROM   [ms].[Playlists]
WHERE
	([PlaylistsId] = @PlaylistsId OR @PlaylistsId IS NULL)
GO
-- ms.usp_PlaylistsItems_delete
CREATE PROC [ms].[usp_PlaylistsItems_delete]
	@SyncID varchar(50)
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare @vTC int = @@TRANCOUNT
BEGIN TRY
	BEGIN TRAN
	DELETE FROM [ms].[PlaylistsItems_sync]
	WHERE SyncID = @SyncID
	COMMIT
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);
	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ms.usp_PlaylistsItems_sync
CREATE PROC [ms].[usp_PlaylistsItems_sync]
    @LastSyncDate datetime = NULL,
    @LastId bigint = NULL,
    @RecCount int = NULL
AS
	SET NOCOUNT ON
	SET XACT_ABORT ON
	IF (@LastSyncDate IS NULL)
		SELECT @LastSyncDate = '1900.01.01'
	SELECT @LastId = ISNULL(@LastId, 0)
	SELECT TOP(CASE
		WHEN ISNULL(@RecCount,0) > 0 THEN @RecCount
		ELSE 1000000000 END) *
	FROM
	(
		SELECT  *	FROM   ms.PlaylistsItems
		WHERE	(EditDate = @LastSyncDate) and PlaylistsItemsId > @LastId
		UNION
		SELECT  *	FROM   ms.PlaylistsItems
		WHERE	(EditDate > @LastSyncDate)
	) a
	ORDER BY EditDate, PlaylistsItemsId
GO
-- ms.usp_PlaylistsItems_update
CREATE PROC [ms].[usp_PlaylistsItems_update]
	@SyncID varchar(50)
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare @vTC int = @@TRANCOUNT
BEGIN TRY
	SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED
	BEGIN TRAN
	SET IDENTITY_INSERT [ms].[PlaylistsItems] ON;
	SELECT * INTO #TmpSync FROM [ms].[PlaylistsItems_sync]
	WHERE SyncID = @SyncID
	merge into [ms].[PlaylistsItems] as Target
	using #TmpSync as Source
	on Target.[PlaylistsItemsId] = Source.PlaylistsItemsId
	when matched then
	UPDATE SET
		Target.[AdMediaId] = Source.AdMediaId, Target.[PlaylistsId] = Source.PlaylistsId,
		Target.[PlayDuration_sec] = Source.PlayDuration_sec, Target.[Seq] = Source.Seq,
		Target.[RecDate] = Source.RecDate, Target.[EditDate] = Source.EditDate, Target.[Enabled] = Source.Enabled, Target.[AdMediaType] = Source.AdMediaType
	when not matched then
	INSERT ([PlaylistsItemsId], [AdMediaId], [PlaylistsId], [PlayDuration_sec], [Seq], [Enabled], [RecDate], [EditDate], [AdMediaType])
	VALUES (Source.PlaylistsItemsId, Source.AdMediaId, Source.PlaylistsId, Source.PlayDuration_sec, Source.Seq, Source.Enabled, Source.RecDate, Source.EditDate, Source.AdMediaType);
	DELETE FROM [ms].[PlaylistsItems_sync]
	WHERE SyncID = @SyncID
	COMMIT
	SET IDENTITY_INSERT [ms].[PlaylistsItems] OFF;
END TRY
BEGIN CATCH
  	DECLARE @ErrorMessage NVARCHAR(4000);
	DECLARE @ErrorSeverity INT;
	DECLARE @ErrorState INT;
	SELECT
		@ErrorMessage = ERROR_MESSAGE(),
		@ErrorSeverity = ERROR_SEVERITY(),
		@ErrorState = ERROR_STATE();
	RAISERROR (@ErrorMessage, -- Message text.
		@ErrorSeverity, -- Severity.
		@ErrorState -- State.
	);
	if @vTC = 0 and @@TRANCOUNT > 0
		ROLLBACK TRANSACTION
END CATCH
GO
-- ms.usp_PlaylistsItems_v
CREATE PROC [ms].[usp_PlaylistsItems_v]
@PlaylistsId bigint = NULL
AS
SET NOCOUNT ON
SET XACT_ABORT ON
SELECT pli.*
	FROM   [ms].[PlaylistsItems] pli
	WHERE
		([PlaylistsId] = @PlaylistsId OR @PlaylistsId IS NULL)
GO
-- ms.usp_Procedures
CREATE PROC [ms].[usp_Procedures]
	@SqlType smallint = null -- 0-lenteles ir viewai,1-proceduros,2-kliento proceduros
AS
SET NOCOUNT ON
SET XACT_ABORT ON
declare @vTC int = @@TRANCOUNT, @vName varchar(255) = 'TOP'
SELECT @SqlType = ISNULL(@SqlType, 2)
-- KONFIGURACIJA: '3001','PARDUOTUVĖ: parduotuvės kodas'
-- SELECT @vName = ValueStr FROM ms.ConfigValues WHERE ConfigTypesId = 3001 AND ConfigId = 3000
if @SqlType = 0
BEGIN
	SELECT CONVERT(VARCHAR(255), name) as ProcName
	FROM sys.sysobjects
	WHERE xtype='U' OR  xtype='V'
	ORDER BY ProcName
END
ELSE
if @SqlType = 1
BEGIN
	SELECT CONVERT(VARCHAR(255), name) as ProcName
	FROM sys.sysobjects
	WHERE xtype='P'
	ORDER BY ProcName
END
ELSE
if @SqlType = 2 AND LEN(@vName) > 0
BEGIN
	SELECT @vName = '%' + @vName + '%'

	SELECT CONVERT(VARCHAR(255), name) as ProcName
	FROM sys.sysobjects
	WHERE xtype='P' AND name LIKE @vName
END
ELSE
	SELECT CONVERT(VARCHAR(255), name) as ProcName
	FROM sys.sysobjects
	WHERE 0 = 1
GO
-- ms.usp_ProceduresParams
CREATE PROC [ms].[usp_ProceduresParams]
	@ProcName varchar(255)
AS
SET NOCOUNT ON
SET XACT_ABORT ON
SELECT @ProcName = 'ms.' + @ProcName
select
   'ParamName' = name,
   'Type'   = type_name(user_type_id),
   'Length'   = max_length,
   'Prec'   = case when type_name(system_type_id) = 'uniqueidentifier'
              then precision
              else OdbcPrec(system_type_id, max_length, precision) end,
   'Scale'   = OdbcScale(system_type_id, scale),
   'ParamOrder'  = parameter_id,
   'Collation'   = convert(sysname,
                   case when system_type_id in (35, 99, 167, 175, 231, 239)
                   then ServerProperty('collation') end)
  from sys.parameters where object_id = object_id(@ProcName)
GO
